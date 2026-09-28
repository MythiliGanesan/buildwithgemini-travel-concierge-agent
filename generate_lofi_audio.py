"""Generates an upbeat lo-fi background music track (lofi_track.wav) using Python standard libraries."""

import math
import struct
import wave

SAMPLE_RATE = 44100
BPM = 80
BEAT_DUR = 60.0 / BPM
BAR_DUR = BEAT_DUR * 4
TOTAL_DURATION = 25.0  # seconds

def note_freq(note_str):
    notes = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    letter = note_str[:-1]
    octave = int(note_str[-1])
    semitones = notes[letter] + (octave - 4) * 12
    return 440.0 * (2 ** ((semitones - 9) / 12.0))

# Upbeat Jazz/Lo-Fi Chords: FM7 - Em7 - Dm7 - Cmaj7
CHORDS = [
    [note_freq('F3'), note_freq('A3'), note_freq('C4'), note_freq('E4')],
    [note_freq('E3'), note_freq('G3'), note_freq('B3'), note_freq('D4')],
    [note_freq('D3'), note_freq('F3'), note_freq('A3'), note_freq('C4')],
    [note_freq('C3'), note_freq('E3'), note_freq('G3'), note_freq('B3')],
]

def generate_track():
    num_samples = int(SAMPLE_RATE * TOTAL_DURATION)
    buffer = [0.0] * num_samples

    for i in range(num_samples):
        t = i / float(SAMPLE_RATE)
        
        # Chord progression loop
        bar_idx = int(t / BAR_DUR) % len(CHORDS)
        chord = CHORDS[bar_idx]
        beat_in_bar = (t % BAR_DUR) / BEAT_DUR

        # Soft warm rhodes/synth chord sound
        chord_val = 0.0
        for freq in chord:
            # Add subtle vibrato
            vib = math.sin(2 * math.pi * 5.0 * t) * 0.8
            phase = 2 * math.pi * (freq + vib) * t
            sine = math.sin(phase) + 0.3 * math.sin(2 * phase) + 0.1 * math.sin(3 * phase)
            chord_val += sine

        # Envelope per beat
        env = math.exp(-3.0 * (beat_in_bar % 1.0))
        chord_val *= 0.15 * env

        # Lo-Fi Drum Beat (Kick on 1 & 3, Snare on 2 & 4, Hi-hat on every 0.5 beat)
        beat_time = t % BEAT_DUR
        kick = 0.0
        snare = 0.0
        hihat = 0.0

        beat_num = int(t / BEAT_DUR) % 4
        if beat_num in [0, 2] and beat_time < 0.15:
            # Kick drum (pitch drop)
            k_freq = 120.0 * math.exp(-30.0 * beat_time)
            kick = math.sin(2 * math.pi * k_freq * beat_time) * math.exp(-15.0 * beat_time) * 0.4

        if beat_num in [1, 3] and beat_time < 0.2:
            # Soft snare / rimshot
            noise = (math.sin(2 * math.pi * 450.0 * t) * 0.5 + (math.sin(17 * t) % 1.0) - 0.5)
            snare = noise * math.exp(-20.0 * beat_time) * 0.25

        if (t % (BEAT_DUR / 2)) < 0.05:
            # Soft hi-hat tick
            hat_t = t % (BEAT_DUR / 2)
            hihat = ((math.sin(8000.0 * hat_t) % 1.0) - 0.5) * math.exp(-60.0 * hat_t) * 0.08

        # Subtle Vinyl Crackle
        crackle = ((math.sin(317 * t) * math.sin(97 * t)) > 0.98) * 0.02

        sample_val = chord_val + kick + snare + hihat + crackle
        buffer[i] = max(-1.0, min(1.0, sample_val))

    with wave.open("lofi_track.wav", "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        for s in buffer:
            int_val = int(s * 32767.0)
            wav_file.writeframes(struct.pack("<h", int_val))

    print("lofi_track.wav generated successfully!")

if __name__ == "__main__":
    generate_track()
