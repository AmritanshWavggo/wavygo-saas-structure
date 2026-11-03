import { describe, it, expect } from 'vitest'
import { validateRcFormat, RC_PATTERN } from '../../utils/rc.js'
import {
  validateAddVehicleForm,
  buildVehicleFormData,
  initialData,
} from './AddVehicle.jsx'

describe('AddVehicle validation and data mapping', () => {
  describe('RC format validation (rc.js)', () => {
    it('accepts standard Indian registration numbers', () => {
      expect(validateRcFormat('GJ05AB4821')).toBe(true)
      expect(validateRcFormat('KA01MN2345')).toBe(true)
      expect(validateRcFormat('MH12DE1432')).toBe(true)
      expect(validateRcFormat('DL01CAA1111')).toBe(true)
      expect(validateRcFormat('HR26DK8337')).toBe(true)
    })

    it('accepts registration numbers with whitespace', () => {
      expect(validateRcFormat('GJ 05 AB 4821')).toBe(true)
      expect(validateRcFormat('  KA 01  MN 2345 ')).toBe(true)
      expect(validateRcFormat('DL 01 C AA 1111')).toBe(true)
    })

    it('rejects invalid or incomplete registration numbers', () => {
      expect(validateRcFormat('GJ05')).toBe(false)
      expect(validateRcFormat('12345')).toBe(false)
      expect(validateRcFormat('ABC')).toBe(false)
      expect(validateRcFormat('GJ0512345678')).toBe(false)
      expect(validateRcFormat('')).toBe(false)
      expect(validateRcFormat(null)).toBe(false)
      expect(validateRcFormat(undefined)).toBe(false)
    })

    it('exports RC_PATTERN matching backend regex', () => {
      expect(RC_PATTERN).toBeInstanceOf(RegExp)
      expect(RC_PATTERN.test('GJ05AB4821')).toBe(true)
    })
  })

  describe('Form step validation (validateAddVehicleForm)', () => {
    const currentYear = new Date().getFullYear()

    it('validates Step 0 required fields and RC format', () => {
      const emptyErrors = validateAddVehicleForm(0, { ...initialData, makeModel: '' }, null)
      expect(emptyErrors.makeModel).toBe('Enter the vehicle make and model.')
      expect(emptyErrors.registration).toBe('Enter the registration number.')
      expect(emptyErrors.type).toBe('Choose a vehicle type.')
      expect(emptyErrors.fuel).toBe('Choose a fuel type.')
      expect(emptyErrors.transmission).toBe('Choose a transmission.')

      const invalidRcErrors = validateAddVehicleForm(
        0,
        {
          ...initialData,
          makeModel: 'Honda Activa 6G',
          registration: 'INVALID',
          year: '2023',
          type: 'Scooter',
          fuel: 'Petrol',
          transmission: 'Automatic',
        },
        null
      )
      expect(invalidRcErrors.registration).toBe('Enter a valid registration number (e.g. GJ05AB4821).')
    })

    it('validates Step 0 model year bounds (2000 to currentYear + 1)', () => {
      const lowYear = validateAddVehicleForm(
        0,
        {
          makeModel: 'Chetak',
          registration: 'MH01AB1234',
          year: '1999',
          type: 'Scooter',
          fuel: 'Petrol',
          transmission: 'Manual',
        },
        null
      )
      expect(lowYear.year).toContain('between 2000 and')

      const highYear = validateAddVehicleForm(
        0,
        {
          makeModel: 'Chetak',
          registration: 'MH01AB1234',
          year: String(currentYear + 2),
          type: 'Scooter',
          fuel: 'Petrol',
          transmission: 'Manual',
        },
        null
      )
      expect(highYear.year).toContain('between 2000 and')

      const validYear = validateAddVehicleForm(
        0,
        {
          makeModel: 'Chetak',
          registration: 'MH01AB1234',
          year: String(currentYear),
          type: 'Scooter',
          fuel: 'Petrol',
          transmission: 'Manual',
        },
        null
      )
      expect(validYear.year).toBeUndefined()
    })

    it('validates Step 1 pricing and location', () => {
      const step1Errors = validateAddVehicleForm(1, { rate: '0', location: '', minimumDays: '0' }, null)
      expect(step1Errors.rate).toBe('Enter a daily rate greater than ₹0.')
      expect(step1Errors.location).toBe('Add a pickup location.')
      expect(step1Errors.minimumDays).toBe('Minimum rental must be at least one day.')
    })

    it('enforces photo type and size limits on Step 2', () => {
      // Disallowed file type (e.g. GIF or PDF)
      const badTypeErrors = validateAddVehicleForm(
        2,
        {},
        { file: { type: 'image/gif', size: 1024 * 1024 } }
      )
      expect(badTypeErrors.photo).toBe('Vehicle photo must be a JPEG, PNG, or WebP image.')

      // Oversized file (> 10MB)
      const oversizedErrors = validateAddVehicleForm(
        2,
        {},
        { file: { type: 'image/jpeg', size: 10 * 1024 * 1024 + 1 } }
      )
      expect(oversizedErrors.photo).toBe('Vehicle photo exceeds the 10 MB limit.')

      // Valid JPEG within limits
      const validPhotoErrors = validateAddVehicleForm(
        2,
        {},
        { file: { type: 'image/jpeg', size: 3 * 1024 * 1024 } }
      )
      expect(validPhotoErrors.photo).toBeUndefined()

      // Optional photo (null) is valid
      const noPhotoErrors = validateAddVehicleForm(2, {}, null)
      expect(noPhotoErrors.photo).toBeUndefined()
    })
  })

  describe('FormData casting and contract mapping (buildVehicleFormData)', () => {
    it('casts string inputs to proper number representations matching backend router schema', () => {
      const mockData = {
        makeModel: 'Royal Enfield Classic 350',
        trim: 'Chrome Bronze',
        registration: 'gj 05 ab 4821',
        year: '2023',
        type: 'Motorcycle',
        fuel: 'Petrol',
        transmission: 'Manual',
        color: 'Chrome Bronze',
        engineCapacity: '349',
        seats: '2',
        rcStatus: 'Verified',
        rate: '1850.75',
        minimumDays: '2',
        location: 'Koramangala 4th Block, Bengaluru',
        pickupNotes: 'Gate passcode 4421',
      }

      const mockPhoto = { file: new File(['photo_bytes'], 'bike.jpg', { type: 'image/jpeg' }) }

      const formData = buildVehicleFormData(mockData, mockPhoto)

      // Strings correctly trimmed and normalized
      expect(formData.get('makeModel')).toBe('Royal Enfield Classic 350')
      expect(formData.get('registration')).toBe('gj 05 ab 4821')
      expect(formData.get('registrationNumber')).toBe('GJ05AB4821')

      // Number types cast to strings properly (integers and float)
      expect(formData.get('year')).toBe('2023')
      expect(formData.get('engineCapacity')).toBe('349')
      expect(formData.get('seats')).toBe('2')
      expect(formData.get('dailyRate')).toBe('1850.75')
      expect(formData.get('minimumDays')).toBe('2')
      expect(formData.get('securityDeposit')).toBe('0')

      // Enums and booleans
      expect(formData.get('type')).toBe('Motorcycle')
      expect(formData.get('fuel')).toBe('Petrol')
      expect(formData.get('transmission')).toBe('Manual')
      expect(formData.get('rcStatus')).toBe('Verified')
      expect(formData.get('showOnWavygo')).toBe('false')
      expect(formData.get('fleetAvailability')).toBe('Available')

      // Photo binary is attached under 'photos'
      expect(formData.get('photos')).toBeTruthy()

      // Documents step is disabled in Phase 1: no documents keys present
      expect(formData.has('documents')).toBe(false)
      expect(formData.has('documentTypes')).toBe(false)
    })

    it('omits engineCapacity when vehicle is Electric or unprovided', () => {
      const electricData = {
        makeModel: 'Ather 450X',
        registration: 'KA01EV1234',
        year: '2024',
        type: 'Electric',
        fuel: 'Electric',
        transmission: 'Automatic',
        engineCapacity: '',
        seats: '2',
        rate: '1200',
        minimumDays: '1',
        location: 'Indiranagar',
      }

      const formData = buildVehicleFormData(electricData, null)
      expect(formData.has('engineCapacity')).toBe(false)
      expect(formData.has('photos')).toBe(false)
    })
  })
})

