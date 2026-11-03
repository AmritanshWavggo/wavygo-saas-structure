import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { vehiclesApi } from '../services/vehiclesApi.js'

export function useVehicles(params = {}) {
  return useQuery({
    queryKey: ['vehicles', params],
    queryFn: () => vehiclesApi.listVehicles(params),
    placeholderData: keepPreviousData,
  })
}

export function useVehicle(id) {
  return useQuery({
    queryKey: ['vehicle', id],
    queryFn: () => vehiclesApi.getVehicle(id),
    enabled: Boolean(id),
  })
}

export function useCreateVehicle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (formData) => vehiclesApi.createVehicle(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
    },
  })
}

export function useUpdateVehicle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, formData }) => vehiclesApi.updateVehicle(id, formData),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      queryClient.invalidateQueries({ queryKey: ['vehicle', variables.id] })
    },
  })
}

export function useToggleShowOnWavygo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, showOnWavygo }) => vehiclesApi.toggleShowOnWavygo(id, showOnWavygo),
    onMutate: async ({ id, showOnWavygo }) => {
      await queryClient.cancelQueries({ queryKey: ['vehicles'] })

      const queryCache = queryClient.getQueryCache()
      const vehicleQueries = queryCache.findAll({ queryKey: ['vehicles'] })
      const previousQueries = vehicleQueries.map((query) => ({
        queryKey: query.queryKey,
        data: query.state.data,
      }))

      // Optimistically update vehicle in all active vehicle lists in cache
      vehicleQueries.forEach((query) => {
        queryClient.setQueryData(query.queryKey, (old) => {
          if (!old?.items) return old
          return {
            ...old,
            items: old.items.map((vehicle) => {
              if (vehicle.id !== id) return vehicle
              return {
                ...vehicle,
                showOnWavygo,
                status: showOnWavygo ? 'Online' : 'Offline',
              }
            }),
          }
        })
      })

      return { previousQueries }
    },
    onError: (_err, _vars, context) => {
      if (context?.previousQueries) {
        context.previousQueries.forEach(({ queryKey, data }) => {
          queryClient.setQueryData(queryKey, data)
        })
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
    },
  })
}

export function useDeleteVehicle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id) => vehiclesApi.deleteVehicle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
    },
  })
}

