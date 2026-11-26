"""Like-for-like *frame* screening, not a proof load or a printed strength rating.
Use STUDY_PROXIES=1 with compact_base.py in FreeCADCmd first. Example:
OPENBLAS_NUM_THREADS=1 python3 compare_frames.py --grid 2 --walls 5 stock. SI-derived units: N, mm, MPa.
Common structured trilinear bricks keep the two drilled lands and fixtures on the same grid.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

WORK = Path(__file__).resolve().parents[1]/'research'/'frame-study'
CORNERS = np.array(list(itertools.product((0, 1), repeat=3)))
SIGNS = 2*CORNERS-1


def raster(path, h):
    dt = np.dtype([('n','<f4',3), ('v','<f4',(3,3)), ('tag','<u2')])
    tris = np.fromfile(path, offset=84, dtype=dt)['v'].astype(float)
    # Centred in Y about the midline. Sample a tiny distance off grid ties.
    lo = np.floor(tris.min(axis=(0,1))/h-1).astype(int)
    hi = np.ceil(tris.max(axis=(0,1))/h+1).astype(int)
    axes = [(np.arange(a,b)+.5)*h for a,b in zip(lo,hi)]
    xx,yy,zz = axes
    solid = np.zeros(tuple(map(len,axes)), dtype=bool)
    yy = yy + .00011; zz = zz + .00017
    for p,q,r in tris:
        u,v=q-p,r-p
        det = u[1]*v[2]-v[1]*u[2]
        if abs(det) < 1e-9: continue
        iy = np.where((yy>=min(p[1],q[1],r[1])) & (yy<=max(p[1],q[1],r[1])))[0]
        iz = np.where((zz>=min(p[2],q[2],r[2])) & (zz<=max(p[2],q[2],r[2])))[0]
        dy,dz = yy[iy,None]-p[1],zz[iz]-p[2]
        a, b = (dy*v[2]-dz*v[1])/det, (dz*u[1]-dy*u[2])/det
        j,k=np.where((a>=0)&(b>=0)&(a+b<=1))
        solid[:,iy[j],iz[k]] ^= (xx[:,None]+.00007 < p[0]+a[j,k]*u[0]+b[j,k]*v[0])
    return lo,solid


def cells(path,h):
    lo,solid=raster(path,h)
    el = np.argwhere(solid)+lo
    nodes, ix = np.unique((el[:,None,:]+CORNERS).reshape(-1,3), axis=0, return_inverse=True)
    return el, nodes*h, ix.reshape(-1,8)


def strain_matrix(pos,h):
    factors = (1+SIGNS*pos)/2
    dx,dy,dz = [SIGNS[:,i]/h*np.prod(factors[:,[(i+1)%3,(i+2)%3]],axis=1) for i in range(3)]
    B=np.zeros((6,24)); B[0,::3]=dx; B[1,1::3]=dy; B[2,2::3]=dz
    B[3,::3]=dy; B[3,1::3]=dx; B[4,1::3]=dz; B[4,2::3]=dy; B[5,::3]=dz; B[5,2::3]=dx
    return B


def material(soft_y):
    # Illustrative isotropic E=2000, nu=.30. Optional sensitivity: halve the
    # modulus across print layers (mounted Y) and both associated shear moduli.
    E,nu=2000.,.30
    S=np.full((3,3),-nu/E); np.fill_diagonal(S,1/E); S[1,1]/=soft_y
    D=np.zeros((6,6)); D[:3,:3]=np.linalg.inv(S)
    D[(3,4,5),(3,4,5)] = E/(2*(1+nu))*np.array([soft_y,soft_y,1])
    return D


def metrics(u,f,edof,B,D,h,centres):
    stress=(u[edof]@B.T)@D.T
    xx,yy,zz,xy,yz,zx = stress.T
    vm = np.sqrt(((xx-yy)**2+(yy-zz)**2+(zz-xx)**2)/2 + 3*(xy**2+yz**2+zx**2))
    S=np.stack((xx,xy,zx,xy,yy,yz,zx,yz,zz),axis=-1).reshape(-1,3,3)
    p=np.linalg.eigvalsh(S)[:,-1].clip(min=0)
    # Same volume of material, not a percentile that changes as mass is removed.
    # Supplement the 300 mm3 hot-volume mean with the raw peak (mesh-sensitive).
    n=max(1,round(300/h**3)); hot=lambda s: float(np.partition(s,-n)[-n:].mean())
    return dict(work_Nmm=float(f@u), max_motion_mm=float(np.linalg.norm(u.reshape(-1,3),axis=1).max()),
                tensile_hot_MPa=hot(p), mises_hot_MPa=hot(vm), layer_tensile_hot_MPa=hot(yy.clip(min=0)),
                tensile_peak_MPa=float(p.max()), mises_peak_MPa=float(vm.max()),
                tensile_peak_at_mm=centres[p.argmax()].tolist(), mises_peak_at_mm=centres[vm.argmax()].tolist())


def shell_fraction(path,el,h,walls):
    # Subvoxel shell fractions in the real print orientation (+Y). Horizontal
    # skin uses 5 top / 3 bottom layers; perimeters follow each XZ contour.
    from scipy.ndimage import distance_transform_edt as edt
    n=round(h/.5); q=h/n; lo,occ=raster(path,q)
    walls_mm=.42+(walls-1)*.45
    skin=np.zeros_like(occ); air=~occ
    for i in range(occ.shape[1]):
        mat=occ[:,i,:]
        if mat.any():skin[:,i,:]=(edt(mat)*q-.5*q < walls_mm)&mat
    for side,dist in ((1,1.),(-1,.6)):
        for k in range(1,round(dist/q)+1):
            skin |= occ & np.roll(air,-side*k,axis=1)
    # PAD (outside the mesh) before gathering a full coarse cell at an edge.
    skin=np.pad(skin,n); occ=np.pad(occ,n); start=el*n-lo+n
    cnt=np.zeros(len(el)); tot=cnt.copy()
    for off in itertools.product(range(n),repeat=3):
        p=tuple((start+off).T);cnt+=skin[p];tot+=occ[p]
    assert np.all(tot>0)
    return cnt/tot


def run(name,h,soft_y,walls=0,infill=.35,power=1.):
    path=WORK/(name+'.stl'); el,nodes,idx=cells(path,h)
    D=material(soft_y); B=strain_matrix(np.zeros(3),h)
    Bs=[strain_matrix(np.asarray(q)/np.sqrt(3),h) for q in itertools.product((-1,1),repeat=3)]
    K=sum(A.T@D@A*h**3/8 for A in Bs)
    # Rigid-body and constant-strain patch sanity checks.
    assert sum(np.linalg.eigvalsh(K)<1e-7)==6 and np.allclose(B@(h*CORNERS).ravel(),[1,1,1,0,0,0])
    edof=(3*idx[:,:,None]+np.arange(3)).reshape(-1,24).astype('i')
    I,J=np.indices((24,24)); nd=len(nodes)*3
    if walls:
        sf=shell_fraction(path,el,h,walls)
        scale=sf+(1-sf)*infill**power
    else:
        scale=np.ones(len(el))
    A=coo_matrix(((scale[:,None]*K.ravel()).ravel(),(edof[:,I.ravel()].ravel(),edof[:,J.ravel()].ravel())),shape=(nd,nd)).tocsc()
    x,y,z=nodes.T
    def disc(x0,y0,lo,hi,z0):
        r=np.hypot(x-x0,y-y0)
        ids=np.where((r>=lo)&(r<=hi)&np.isclose(z,np.rint(z0/h)*h))[0]
        assert len(ids)>=6,(name,z0,lo,hi,len(ids))
        return ids
    lift = 24 if name.endswith('28') else 16 if name.endswith('36') else 0
    screws=[disc(13,t,8,11.8,-54+lift) for t in (-40,40)]
    desk=np.concatenate([disc(13,t,0,8.,0) for t in (-40,40)])
    yaw=disc(48,0,12.5,20.5,12)
    def force(ids,force=(0,0,0),moment=(0,0,0)):
        # Uniform force plus an exactly self-equilibrated moment about the ring centre.
        f=np.zeros_like(nodes,dtype=float); rr=nodes[ids]-nodes[ids].mean(axis=0)
        inertia=(np.eye(3)*np.sum(rr*rr)-rr.T@rr)
        f[ids]=np.array(force)/len(ids)+np.cross(np.linalg.solve(inertia,moment),rr)
        assert np.allclose(f.sum(axis=0),force) and np.allclose(np.cross(rr,f[ids]).sum(axis=0),moment)
        return f.ravel()
    fL,fR=[force(ids,(0,0,-100)) for ids in screws]
    # Unit-like comparison loads, not a claim of screw preload or a load rating.
    pitch=force(yaw,(0,0,-10),(0,2000,0)); roll=force(yaw,(0,0,-10),(2000,0,0))
    twist=force(yaw,(0,10,0),(0,0,2000))
    cases={}
    for ids,loads in [(desk,{'even_clamp':fL+fR,'one_screw':fL,
                             'clamp_and_pitch':fL+fR+pitch,'clamp_and_roll':fL+fR+roll,
                             'clamp_and_yaw':fL+fR+twist}),
                      (np.concatenate(screws),{'pitch':pitch,'roll':roll,'yaw':twist})]:
        fixed=(3*ids[:,None]+np.arange(3)).ravel()
        free=np.setdiff1d(np.arange(nd),fixed)
        lu=splu(A[free,:][:,free].tocsc(),permc_spec='MMD_AT_PLUS_A')
        for key,f in loads.items():
            u=np.zeros(nd); u[free]=lu.solve(f[free]); r=A@u-f
            assert np.max(abs(r[free]))<1e-6 and np.allclose(r.reshape(-1,3).sum(axis=0),-f.reshape(-1,3).sum(axis=0),atol=1e-6)
            cases[key]=metrics(u,f,edof,B,D,h,(el+.5)*h)
        del lu
    out=dict(name=name,grid_mm=h,layer_ratio=soft_y,bricks=len(idx),proxy_mesh_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
             voxel_volume_cm3=len(idx)*h**3/1000,cases=cases)
    out.update(walls=walls,infill=infill if walls else None,core_exponent=power if walls else None)
    tag=f'-w{walls}-i{infill:g}-p{power:g}' if walls else ''
    (WORK/f'{name}-h{h:g}-y{soft_y:g}{tag}.json').write_text(json.dumps(out,indent=2)+'\n')
    print(name,h,soft_y,len(el),'done',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('names',nargs='+'); p.add_argument('--grid',type=float,default=3)
    p.add_argument('--layer-ratio',type=float,default=1,choices=(.5,1.)); p.add_argument('--walls',type=int,default=0); p.add_argument('--infill',type=float,default=.35); p.add_argument('--core-power',type=float,choices=(1.,2.),default=1.); a=p.parse_args()
    for name in a.names: run(name,a.grid,a.layer_ratio,a.walls,a.infill,a.core_power)
