const _ENDPOINT = 'c410d179b056797269a4a2188bdf8a48';
export const ENDPOINT = _ENDPOINT.startsWith('http')
  ? _ENDPOINT
  : `http://localhost:8000`;
