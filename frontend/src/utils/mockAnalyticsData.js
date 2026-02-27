// Generate mock fantasy football analytics data for testing
// The helper below is currently unused by our smoke tests but provides
// a way to quickly prototype charts during development.

export function generateDraftValueData() {
  const positions = ['QB', 'RB', 'WR', 'TE'];
  const sampleNames = [
    'Player A',
    'Player B',
    'Player C',
    'Player D',
    'Player E',
  ];
  return sampleNames.map((name, idx) => {
    const pos = positions[idx % positions.length];
    const adp = 1 + Math.floor(Math.random() * 150);
    const projectedPoints = 100 + Math.floor(Math.random() * 250);
    return { name, position: pos, adp, projectedPoints };
  });
}
