import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('api client refresh interceptor', () => {
  let requestInterceptor;
  let responseErrorInterceptor;
  let mockClient;

  beforeEach(async () => {
    requestInterceptor = undefined;
    responseErrorInterceptor = undefined;

    mockClient = {
      interceptors: {
        request: {
          use: vi.fn((onFulfilled) => {
            requestInterceptor = onFulfilled;
          }),
        },
        response: {
          use: vi.fn((_onFulfilled, onRejected) => {
            responseErrorInterceptor = onRejected;
          }),
        },
      },
      post: vi.fn(),
      request: vi.fn(),
    };

    vi.resetModules();
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => mockClient),
      },
    }));

    vi.unmock('../src/api/client');
    await import('../src/api/client');
  });

  it('refreshes once on 401 and retries the original request', async () => {
    mockClient.post.mockResolvedValue({ data: { access_token: 'new-token' } });
    mockClient.request.mockResolvedValue({ data: { ok: true } });

    const result = await responseErrorInterceptor({
      response: { status: 401 },
      config: { method: 'get', url: '/players' },
    });

    expect(result).toEqual({ data: { ok: true } });
    expect(mockClient.post).toHaveBeenCalledWith(
      '/auth/refresh',
      {},
      expect.objectContaining({ _skipAuthRefresh: true })
    );
    expect(mockClient.request).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'get',
        url: '/players',
        _authRetryAttempted: true,
      })
    );
  });

  it('does not try to refresh when /auth/refresh itself returns 401', async () => {
    await expect(
      responseErrorInterceptor({
        response: { status: 401 },
        config: { method: 'post', url: '/auth/refresh' },
      })
    ).rejects.toMatchObject({ response: { status: 401 } });

    expect(mockClient.post).not.toHaveBeenCalled();
    expect(mockClient.request).not.toHaveBeenCalled();
  });

  it('attaches csrf token header for state-changing requests', async () => {
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      value: 'ffpi_csrf_token=test-csrf-token',
    });

    const config = await requestInterceptor({ method: 'post', headers: {} });
    expect(config.headers['X-CSRF-Token']).toBe('test-csrf-token');
  });
});
