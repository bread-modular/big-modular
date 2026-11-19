// How loud a hit sounds: a loudness model for the host tools (calibrate.cpp
// and the tests; not in the firmware). A meter does not say it: a noisy hit
// sounds louder than a tonal one at the same RMS (the ear adds up what falls
// into different critical bands), and the ear is 7 .. 12 dB less sensitive at
// 6 .. 10 kHz, where a crash sits, than at 1 kHz.
//
// After Glasberg & Moore, "A model of loudness applicable to time-varying
// sounds" (J. Audio Eng. Soc. 50, 2002), simplified:
//   1. 21 ms Hann frames every 2 ms -> power spectrum;
//   2. weighted with the inverse ISO 226:2003 equal-loudness contour at
//      80 phon (instead of the model's outer and middle ear filters: tones
//      on that contour come out equally loud);
//   3. excitation pattern on the ERB scale, four channels per ERB, rounded-
//      exponential auditory filters whose lower skirt widens with the level;
//   4. specific loudness C ((E + A)^0.2 - A^0.2), summed over the channels:
//      the loudness of the frame in sone (C: 1 kHz at 40 dB SPL = 1 sone);
//   5. short-term loudness (attack 22 ms, release 50 ms); its maximum is the
//      loudness of the hit, returned as a loudness level in phon.
// Checked: 1 kHz at 40 / 60 / 80 dB SPL = 40 / 62 / 81 phon, white noise at
// 60 dB SPL = 77 phon. It ranks hits against each other; it is not a
// certified loudness meter.
#pragma once

#include <cmath>
#include <complex>
#include <cstddef>
#include <vector>

namespace loudness {

static const double SAMPLE_RATE = 48000.0;
// Playback level: a full-scale sine. The hits then peak around 95 dB SPL
// (loud monitors); 10 dB more or less moves the result by under 0.5 phon
// between a crash and a clap.
static const double FULL_SCALE_SPL = 97.0;
static const double CONTOUR_PHON = 80.0;

// ISO 226:2003, table 1.
static const int ISO_POINTS = 29;
static const double ISO_HZ[ISO_POINTS] = {20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
                                          630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500};
static const double ISO_AF[ISO_POINTS] = {0.532, 0.506, 0.480, 0.455, 0.432, 0.409, 0.387, 0.367, 0.349, 0.330,
                                          0.315, 0.301, 0.288, 0.276, 0.267, 0.259, 0.253, 0.250, 0.246, 0.244,
                                          0.243, 0.243, 0.243, 0.242, 0.242, 0.245, 0.254, 0.271, 0.301};
static const double ISO_LU[ISO_POINTS] = {-31.6, -27.2, -23.0, -19.1, -15.9, -13.0, -10.3, -8.1, -6.2, -4.5,
                                          -3.1, -2.0, -1.1, -0.4, 0.0, 0.3, 0.5, 0.0, -2.7, -4.1,
                                          -1.0, 1.7, 2.5, 1.2, -2.1, -7.1, -11.2, -10.7, -3.1};
static const double ISO_TF[ISO_POINTS] = {78.5, 68.7, 59.5, 51.1, 44.0, 37.5, 31.5, 26.5, 22.1, 17.9,
                                          14.4, 11.4, 8.6, 6.2, 4.4, 3.0, 2.2, 2.4, 3.5, 1.7,
                                          -1.3, -4.2, -6.0, -5.4, -1.5, 6.0, 12.6, 13.9, 12.3};

// Sound pressure level of a tone at table point i with a loudness level of phon.
inline double contourSpl(int i, double phon) {
    const double af = 4.47e-3 * (pow(10.0, 0.025 * phon) - 1.15) + pow(0.4 * pow(10.0, (ISO_TF[i] + ISO_LU[i]) / 10.0 - 9.0), ISO_AF[i]);
    return 10.0 / ISO_AF[i] * log10(af) - ISO_LU[i] + 94.0;
}

// What the ear makes of hz re 1 kHz, dB: the contour upside down. Above the
// table (12.5 kHz) hearing falls away, here with 24 dB / octave.
inline double earWeightDb(double hz) {
    if (hz < ISO_HZ[0]) return -100.0;
    if (hz >= ISO_HZ[ISO_POINTS - 1]) {
        return CONTOUR_PHON - contourSpl(ISO_POINTS - 1, CONTOUR_PHON) - 24.0 * log2(hz / ISO_HZ[ISO_POINTS - 1]);
    }
    int i = 0;
    while (ISO_HZ[i + 1] < hz) i++;
    const double t = log(hz / ISO_HZ[i]) / log(ISO_HZ[i + 1] / ISO_HZ[i]);
    return CONTOUR_PHON - (contourSpl(i, CONTOUR_PHON) + t * (contourSpl(i + 1, CONTOUR_PHON) - contourSpl(i, CONTOUR_PHON)));
}

// Equivalent rectangular bandwidth of the auditory filter at hz, and the
// frequency at a position on the ERB-number scale.
inline double erbHz(double hz) { return 24.7 * (4.37 * hz / 1000.0 + 1.0); }
inline double erbNumberToHz(double erbs) { return (pow(10.0, erbs / 21.4) - 1.0) * 1000.0 / 4.37; }

inline void fft(std::vector<std::complex<double>> &a) {
    const size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (size_t len = 2; len <= n; len <<= 1) {
        const std::complex<double> step = std::polar(1.0, -6.283185307179586 / (double)len);
        for (size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0);
            for (size_t j = 0; j < len / 2; j++) {
                const std::complex<double> u = a[i + j], v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= step;
            }
        }
    }
}

struct Model {
    static const size_t FRAME = 1024;           // 21 ms
    static const size_t HOP = 96;               // 2 ms
    static const size_t BINS = FRAME / 2;

    std::vector<double> window, weight;         // Hann; the ear's weight per bin (power)
    std::vector<double> centre, slope;          // channels: centre frequency, p = 4 fc / ERB
    double scale = 0;                           // bin power -> 10^(dB SPL / 10)
    double c = 1;                               // specific loudness constant

    Model() {
        window.resize(FRAME);
        for (size_t i = 0; i < FRAME; i++) window[i] = 0.5 - 0.5 * cos(6.283185307179586 * (double)i / FRAME);
        weight.assign(BINS, 0.0);
        for (size_t k = 1; k < BINS; k++) weight[k] = pow(10.0, earWeightDb(k * SAMPLE_RATE / FRAME) / 10.0);
        for (double erbs = 1.75; erbs < 39.01; erbs += 0.25) {   // 48 Hz .. 15 kHz
            centre.push_back(erbNumberToHz(erbs));
            slope.push_back(4.0 * centre.back() / erbHz(centre.back()));
        }
        // a sine of amplitude 1 puts 1.5 (FRAME / 4)^2 into the three bins of its Hann lobe
        scale = pow(10.0, FULL_SCALE_SPL / 10.0) / (1.5 * FRAME * FRAME / 16.0);
        // 1 kHz at 40 dB SPL = 1 sone
        std::vector<double> tone(SAMPLE_RATE / 2);
        const double amp = pow(10.0, (40.0 - FULL_SCALE_SPL) / 20.0);
        for (size_t i = 0; i < tone.size(); i++) tone[i] = amp * sin(6.283185307179586 * 1000.0 * (double)i / SAMPLE_RATE);
        c = 1.0 / sone(tone);
    }

    // Loudness of one frame (the FRAME samples before `end`), sone.
    double frame(const std::vector<double> &s, size_t end) const {
        std::vector<std::complex<double>> a(FRAME);
        bool silent = true;
        for (size_t i = 0; i < FRAME; i++) {
            const long at = (long)end + (long)i - (long)FRAME;
            const double x = at >= 0 && (size_t)at < s.size() ? s[(size_t)at] : 0.0;
            a[i] = x * window[i];
            silent &= x == 0.0;
        }
        if (silent) return 0.0;
        fft(a);
        // power per bin as the ear takes it, and the level per ERB around each bin
        std::vector<double> power(BINS, 0.0), sum(BINS + 1, 0.0), level(BINS, 0.0);
        for (size_t k = 1; k < BINS; k++) power[k] = std::norm(a[k]) * weight[k] * scale;
        for (size_t k = 0; k < BINS; k++) sum[k + 1] = sum[k] + power[k];
        for (size_t k = 1; k < BINS; k++) {
            const double hz = k * SAMPLE_RATE / FRAME, half = erbHz(hz) / 2.0;
            long lo = (long)floor((hz - half) * FRAME / SAMPLE_RATE), hi = (long)ceil((hz + half) * FRAME / SAMPLE_RATE);
            lo = lo < 0 ? 0 : lo;
            hi = hi >= (long)BINS ? (long)BINS - 1 : hi;
            level[k] = 10.0 * log10(sum[hi + 1] - sum[lo] + 1e-12);
        }
        const double quiet = 1e-9 * sum[BINS];  // bins that add nothing
        const double slope1k = 4.0 * 1000.0 / erbHz(1000.0);
        static const double A = 4.62, ALPHA = 0.2;
        double total = 0.0;
        for (size_t ch = 0; ch < centre.size(); ch++) {
            const double fc = centre[ch], p = slope[ch];
            double excitation = 0.0;
            for (size_t k = 1; k < BINS; k++) {
                if (power[k] <= quiet) continue;
                const double hz = k * SAMPLE_RATE / FRAME;
                double pg = p * fabs(hz - fc) / fc;
                // the lower skirt of the filter widens above 51 dB per ERB
                if (hz < fc) pg *= 1.0 - 0.35 / slope1k * (level[k] - 51.0);
                if (pg < 30.0) excitation += power[k] * (1.0 + pg) * exp(-pg);
            }
            total += pow(excitation + A, ALPHA) - pow(A, ALPHA);
        }
        return c * total * 0.25;                // four channels per ERB
    }

    // Loudness of a hit: the maximum of its short-term loudness, sone.
    // Samples +-1.0 = full scale, at SAMPLE_RATE.
    double sone(const std::vector<double> &s) const {
        const double attack = 1.0 - pow(1.0 - 0.045, 2.0), release = 1.0 - pow(1.0 - 0.02, 2.0);   // per 2 ms
        double shortTerm = 0.0, best = 0.0;
        for (size_t end = HOP; end < s.size() + FRAME; end += HOP) {
            const double now = frame(s, end);
            shortTerm += (now > shortTerm ? attack : release) * (now - shortTerm);
            best = shortTerm > best ? shortTerm : best;
        }
        return best;
    }

    // ... as a loudness level: 10 phon more = twice as loud.
    double phon(const std::vector<double> &s) const {
        const double n = sone(s);
        return n >= 1.0 ? 40.0 + 10.0 * log2(n) : 40.0 * pow(n + 0.0005, 0.35);
    }
};

}  // namespace loudness
