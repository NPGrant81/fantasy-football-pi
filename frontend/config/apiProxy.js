export const apiPrefixes = [
  '/auth', '/draft/', '/draft-pick', '/draft-history',
  '/admin/tools', '/admin/nfl', '/admin/live-scoring', '/admin/drafts',
  '/admin/config', '/admin/create-test-league', '/admin/reset-draft',
  '/admin/finalize-draft', '/admin/reset-league',
  '/team/', '/leagues', '/players', '/advisor', '/dashboard', '/waivers/',
  '/trades', '/scoring', '/keepers/', '/playoffs/', '/analytics/', '/nfl',
  '/feedback', '/bug-reports', '/etl', '/api/etl', '/matchups/', '/news',
  '/live-scoring', '/health',
];

export function bypassDocumentRequest(request) {
  if (
    ['GET', 'HEAD'].includes(request.method) &&
    String(request.headers.accept || '').includes('text/html')
  ) {
    return '/index.html';
  }
}

export function createApiProxy(target) {
  return Object.fromEntries(
    apiPrefixes.map((prefix) => [
      `^${prefix.replace(/\/$/, '')}(?:/|\\?|$)`,
      { target, bypass: bypassDocumentRequest },
    ])
  );
}
