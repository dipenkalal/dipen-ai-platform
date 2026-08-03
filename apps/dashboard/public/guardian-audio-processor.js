class GuardianAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.frameSamples = 320;
    this.pending = [];
    this.phase = 0;
  }

  process(inputs) {
    const input = inputs[0];

    if (!input || !input[0]) {
      return true;
    }

    const channel = input[0];
    const ratio = sampleRate / this.targetRate;

    for (let outputIndex = 0; ; outputIndex += 1) {
      const sourcePosition = this.phase + outputIndex * ratio;
      const sourceIndex = Math.floor(sourcePosition);

      if (sourceIndex >= channel.length) {
        this.phase = sourcePosition - channel.length;
        break;
      }

      const nextIndex = Math.min(sourceIndex + 1, channel.length - 1);
      const fraction = sourcePosition - sourceIndex;
      const sample = channel[sourceIndex] +
        (channel[nextIndex] - channel[sourceIndex]) * fraction;
      this.pending.push(Math.max(-1, Math.min(1, sample)));
    }

    while (this.pending.length >= this.frameSamples) {
      const frame = new Int16Array(this.frameSamples);
      let energy = 0;

      for (let index = 0; index < this.frameSamples; index += 1) {
        const sample = this.pending[index];
        energy += sample * sample;
        frame[index] = sample < 0
          ? Math.round(sample * 0x8000)
          : Math.round(sample * 0x7fff);
      }

      this.pending.splice(0, this.frameSamples);
      const level = Math.min(1, Math.sqrt(energy / this.frameSamples) * 6);
      this.port.postMessage(
        {
          type: "audio",
          pcm: frame.buffer,
          level,
        },
        [frame.buffer],
      );
    }

    return true;
  }
}

registerProcessor("guardian-audio-processor", GuardianAudioProcessor);
