import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { bookingsApi } from '../services/bookingsApi.js'

export function useBookings(params = {}) {
  return useQuery({
    queryKey: ['bookings', params],
    queryFn: () => bookingsApi.listBookings(params),
    placeholderData: keepPreviousData,
  })
}

export function useBooking(id) {
  return useQuery({
    queryKey: ['booking', id],
    queryFn: () => bookingsApi.getBooking(id),
    enabled: Boolean(id),
  })
}

export function useCreateBooking() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data) => bookingsApi.createBooking(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      queryClient.invalidateQueries({ queryKey: ['customer-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useUpdateBooking() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }) => bookingsApi.updateBooking(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['booking', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      queryClient.invalidateQueries({ queryKey: ['customer-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useTransitionBookingStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, statusData }) => bookingsApi.transitionStatus(id, statusData),
    // Strictly no optimistic updates for transitions (as approved in plan)
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['booking', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      queryClient.invalidateQueries({ queryKey: ['vehicle'] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      queryClient.invalidateQueries({ queryKey: ['customer-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteBooking() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id) => bookingsApi.deleteBooking(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      queryClient.invalidateQueries({ queryKey: ['customer-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

