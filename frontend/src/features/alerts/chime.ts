/** Synthesized locally: no audio files, downloads or external services. */
export class AlertChime {
  private context: AudioContext | undefined;
  private last = -Infinity;

  async enable() {
    this.context ??= new AudioContext();
    await this.context.resume();
    if (this.context.state !== "running") throw new Error("Sound is blocked by the browser.");
  }

  play() {
    const context = this.context;
    if (!context || context.state !== "running" || Date.now() - this.last < 8000) return;
    this.last = Date.now();
    for (const [offset, frequency] of [
      [0, 660],
      [0.18, 880],
    ] as const) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      const start = context.currentTime + offset;
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.12, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.4);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.42);
      oscillator.onended = () => {
        oscillator.disconnect();
        gain.disconnect();
      };
    }
  }

  close() {
    void this.context?.close();
  }
}
