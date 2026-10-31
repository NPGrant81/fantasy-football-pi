import { act, renderHook, waitFor } from '@testing-library/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { expect, it, vi } from 'vitest';
import apiClient from '../src/api/client';

it('retains the actual query error contract', async () => {
  const failure = new Error('Unavailable');
  apiClient.get.mockRejectedValueOnce(failure);
  const { result } = renderHook(() => useQuery({
    queryKey: ['error-contract'],
    queryFn: () => apiClient.get('/probe'),
  }));
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.error).toBe(failure);
});

it('refetches an active query after a successful mutation invalidates it', async () => {
  apiClient.get.mockResolvedValueOnce({ data: ['before'] }).mockResolvedValueOnce({ data: ['after'] });
  apiClient.post.mockResolvedValueOnce({ data: {} });
  const { result } = renderHook(() => {
    const client = useQueryClient();
    const query = useQuery({
      queryKey: ['mutation-contract'],
      queryFn: async () => (await apiClient.get('/probe')).data,
    });
    const mutation = useMutation({
      mutationFn: () => apiClient.post('/probe'),
      onSuccess: () => client.invalidateQueries({ queryKey: ['mutation-contract'] }),
    });
    return { query, mutation };
  });
  await waitFor(() => expect(result.current.query.data).toEqual(['before']));
  await act(async () => result.current.mutation.mutateAsync());
  await waitFor(() => expect(result.current.query.data).toEqual(['after']));
});

it('does not share cached query data between independent renders', async () => {
  const fetchValue = vi.fn().mockResolvedValueOnce('first').mockResolvedValueOnce('second');
  const useValue = () => useQuery({ queryKey: ['same-key'], queryFn: fetchValue, staleTime: Infinity });
  const first = renderHook(useValue);
  await waitFor(() => expect(first.result.current.data).toBe('first'));
  const second = renderHook(useValue);
  await waitFor(() => expect(second.result.current.data).toBe('second'));
});
