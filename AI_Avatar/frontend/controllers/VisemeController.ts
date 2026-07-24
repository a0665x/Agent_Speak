export class VisemeUnavailableError extends Error {
  constructor() {
    super('viseme animation is unavailable in the motion lab MVP');
    this.name = 'VisemeUnavailableError';
  }
}

export class VisemeController {
  constructor(readonly enabled = false) {}

  setViseme(_viseme: string): void {
    if (!this.enabled) {
      throw new VisemeUnavailableError();
    }
  }
}
