#pragma once
#include "midi.h"
#include "audio/manager.h"
#include "audio/gen/AudioGenerator.h"
#include "audio/env/Envelope.h"

class Voice {
    private:
        AudioGenerator** generators;
        uint8_t totalGenerators;
        float generatorScale;  // 1 / totalGenerators (no divide per sample)
        Envelope* ampEnvelope;
        Envelope* filterEnvelope;
        uint8_t currentNote;
        uint8_t voiceId;
        static uint8_t voiceIdCounter;
        std::function<void(Voice*)> onCompleteCallback = nullptr;
        float velocity = 1.0f;

        float waveform = 0;
        
    public:
        Voice(uint8_t totalGenerators, AudioGenerator* generators[], Envelope* ampEnvelope, Envelope* filterEnvelope)
            : totalGenerators(totalGenerators), generatorScale(1.0f / totalGenerators),
              ampEnvelope(ampEnvelope), filterEnvelope(filterEnvelope) {
                this->generators = new AudioGenerator*[totalGenerators];
                for (uint8_t i = 0; i < totalGenerators; ++i) {
                    this->generators[i] = generators[i];
                }
                voiceId = voiceIdCounter++;
            }

        ~Voice() {
            delete[] generators;
        }

        void init(AudioManager* audioManager) {
            currentNote = 48;
            float freq = MIDI::midiNoteToHz(currentNote);

            for (uint8_t i = 0; i < totalGenerators; ++i) {
                generators[i]->init(audioManager);
                generators[i]->setFrequencyHz(freq);
            }
            ampEnvelope->init(audioManager);
            ampEnvelope->setOnCompleteCallback([this]() { this->onEnvelopeComplete(); });
        }


        void changeGenerators(AudioGenerator* generators[]) {
            float freq = MIDI::midiNoteToHz(currentNote);
            // Configure the incoming generator *before* publishing the pointer
            // so the audio core never observes an uninitialized generator.
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                generators[i]->reset();
                generators[i]->setFrequencyHz(freq);
                this->generators[i] = generators[i];
            }
        }

        void setOnCompleteCallback(std::function<void(Voice*)> callback) {
            this->onCompleteCallback = callback;
        }

        void setNoteOn(float velocity, uint8_t note, uint8_t* generatorNotes = nullptr) {
            this->velocity = velocity;
            currentNote = note;
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                // Exact pitch: whole-hertz notes put chords out of tune
                // (the BM generators still round inside setFrequencyHz()).
                float freq;
                if (generatorNotes) {
                    freq = MIDI::midiNoteToHz(generatorNotes[i]);
                } else {
                    freq = MIDI::midiNoteToHz(note);
                }
                generators[i]->setFrequencyHz(freq);
            }
            ampEnvelope->setTrigger(true);
            filterEnvelope->setTrigger(true);
        }

        void setNoteOff(uint8_t note) {
            if (note == currentNote) {
                ampEnvelope->setTrigger(false);
                filterEnvelope->setTrigger(false);
            }
        }

        float process() {
            // An idle voice is silent: skip its generators (9 wavetable
            // voices are most of the audio core's time).
            if (!ampEnvelope->isActive()) {
                waveform = 0;
                return 0.0f;
            }

            float sum = 0;
            for (uint8_t i = 0; i < totalGenerators; ++i) {
                sum += generators[i]->getSample();
            }
             
            waveform = sum * generatorScale;
            return ampEnvelope->process(waveform) * velocity;
        }

        int16_t getWaveformOnly() {
            return waveform;
        }

        // Envelope level x velocity of the last process() sample.
        float getLevel() {
            return ampEnvelope->getLevel() * velocity;
        }

        Envelope* getAmpEnvelope() {
            return ampEnvelope;
        }

        Envelope* getFilterEnvelope() {
            return filterEnvelope;
        }

        uint8_t getCurrentNote() {
            return currentNote;
        }

        uint8_t getVoiceId() {
            return voiceId;
        }

        void onEnvelopeComplete() {
            if (onCompleteCallback) {
                onCompleteCallback(this);
            }
        }
};

uint8_t Voice::voiceIdCounter = 0;