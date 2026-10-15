import { createContext, useContext, useState } from 'react'

const DemoDataContext = createContext(null)

const initialVehicles = [
  { id: 'VH-1042', name: 'Honda Activa 6G', registration: 'GJ 05 AB 4821', type: 'Scooter', fuel: 'Petrol', year: 2024, color: 'Matte blue', engineCapacity: 110, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 649, image: '🛵' },
  { id: 'VH-1038', name: 'Royal Enfield Classic 350', registration: 'GJ 05 CD 7194', type: 'Motorcycle', fuel: 'Petrol', year: 2023, color: 'Chrome red', engineCapacity: 349, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Rented', price: 1899, image: '🏍️' },
  { id: 'VH-1034', name: 'Ather 450X', registration: 'GJ 05 EF 3602', type: 'Electric', fuel: 'Electric', year: 2025, color: 'Cosmic black', engineCapacity: null, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 1199, image: '🛵' },
  { id: 'VH-1029', name: 'TVS Jupiter', registration: 'GJ 05 GH 2351', type: 'Scooter', fuel: 'Petrol', year: 2022, color: 'Titanium grey', engineCapacity: 110, rcStatus: 'Pending review', seats: 2, status: 'Offline', availability: 'Available', price: 599, image: '🛵' },
  { id: 'VH-1022', name: 'Yamaha FZ-S FI', registration: 'GJ 05 JK 8610', type: 'Motorcycle', fuel: 'Petrol', year: 2024, color: 'Racing blue', engineCapacity: 149, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Maintenance', price: 999, image: '🏍️' },
  { id: 'VH-1018', name: 'Bajaj Pulsar N160', registration: 'GJ 05 LM 4073', type: 'Motorcycle', fuel: 'Petrol', year: 2025, color: 'Brooklyn black', engineCapacity: 164, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 1099, image: '🏍️' },
]

const initialCustomers = [
  { id: 'CU-2048', name: 'Aarav Mehta', phone: '+91 98765 43210', email: 'aarav.mehta@email.com', bookings: 14, active: 1, paid: 28650, pending: 0, status: 'Verified' },
  { id: 'CU-2047', name: 'Isha Patel', phone: '+91 97654 32109', email: 'isha.patel@email.com', bookings: 9, active: 1, paid: 19450, pending: 1200, status: 'Verified' },
  { id: 'CU-2046', name: 'Rohan Shah', phone: '+91 96543 21098', email: 'rohan.shah@email.com', bookings: 6, active: 0, paid: 12800, pending: 0, status: 'Verified' },
  { id: 'CU-2045', name: 'Ananya Desai', phone: '+91 95432 10987', email: 'ananya.desai@email.com', bookings: 3, active: 0, paid: 6200, pending: 850, status: 'Review' },
  { id: 'CU-2044', name: 'Kabir Joshi', phone: '+91 94321 09876', email: 'kabir.j@email.com', bookings: 2, active: 0, paid: 3700, pending: 0, status: 'Verified' },
]

const initialBookings = [
  { id: 'BK-3984', customer: 'Aarav Mehta', vehicle: 'Royal Enfield Classic 350', dates: 'Oct 12 – Oct 14', type: 'Online', status: 'Active', paid: 3798, pending: 0 },
  { id: 'BK-3983', customer: 'Isha Patel', vehicle: 'Honda Activa 6G', dates: 'Oct 12 – Oct 13', type: 'Offline', status: 'Active', paid: 649, pending: 1200 },
  { id: 'BK-3982', customer: 'Rohan Shah', vehicle: 'Ather 450X', dates: 'Oct 11 – Oct 12', type: 'Online', status: 'Completed', paid: 2398, pending: 0 },
  { id: 'BK-3981', customer: 'Ananya Desai', vehicle: 'Bajaj Pulsar N160', dates: 'Oct 11 – Oct 14', type: 'Offline', status: 'Active', paid: 2198, pending: 850 },
  { id: 'BK-3980', customer: 'Kabir Joshi', vehicle: 'TVS Jupiter', dates: 'Oct 10 – Oct 11', type: 'Online', status: 'Completed', paid: 599, pending: 0 },
  { id: 'BK-3979', customer: 'Neha Shah', vehicle: 'Yamaha FZ-S FI', dates: 'Oct 09 – Oct 10', type: 'Online', status: 'Cancelled', paid: 0, pending: 0 },
]

const initialPayments = [
  { id: 'TX-7082', booking: 'BK-3984', customer: 'Aarav Mehta', method: 'UPI', date: 'Oct 12, 2026', amount: 3798, status: 'Paid' },
  { id: 'TX-7081', booking: 'BK-3983', customer: 'Isha Patel', method: 'Cash', date: 'Oct 12, 2026', amount: 649, status: 'Partial' },
  { id: 'TX-7080', booking: 'BK-3982', customer: 'Rohan Shah', method: 'Card', date: 'Oct 11, 2026', amount: 2398, status: 'Paid' },
  { id: 'TX-7079', booking: 'BK-3981', customer: 'Ananya Desai', method: 'UPI', date: 'Oct 11, 2026', amount: 2198, status: 'Partial' },
  { id: 'TX-7078', booking: 'BK-3980', customer: 'Kabir Joshi', method: 'UPI', date: 'Oct 10, 2026', amount: 599, status: 'Paid' },
]

const initialDocuments = [
  { id: 'DC-104', name: 'Business registration', category: 'Shop License', date: 'Sep 24, 2026', status: 'Verified', scope: 'Business' },
  { id: 'DC-103', name: 'GST registration certificate', category: 'GST Certificate', date: 'Sep 18, 2026', status: 'Verified', scope: 'Business' },
  { id: 'DC-102', name: 'Owner PAN card', category: 'PAN Card', date: 'Sep 18, 2026', status: 'In review', scope: 'Business' },
  { id: 'DC-101', name: 'Activa 6G insurance', category: 'Insurance', date: 'Aug 30, 2026', status: 'Expires soon', scope: 'Vehicle' },
  { id: 'DC-100', name: 'Classic 350 RC book', category: 'RC Book', date: 'Aug 22, 2026', status: 'Verified', scope: 'Vehicle' },
]

const initialMaintenance = [
  { id: 'MT-081', vehicle: 'Yamaha FZ-S FI', type: 'Scheduled servicing', start: 'Oct 12, 2026', expected: 'Oct 14, 2026', cost: 2400, payment: 'Paid', status: 'Ongoing' },
  { id: 'MT-080', vehicle: 'TVS Jupiter', type: 'Brake inspection', start: 'Oct 10, 2026', expected: 'Oct 11, 2026', cost: 950, payment: 'Paid', status: 'Completed' },
  { id: 'MT-079', vehicle: 'Ather 450X', type: 'Tyre replacement', start: 'Oct 07, 2026', expected: 'Oct 08, 2026', cost: 3800, payment: 'Pending', status: 'Completed' },
  { id: 'MT-078', vehicle: 'Honda Activa 6G', type: 'Oil change', start: 'Oct 02, 2026', expected: 'Oct 02, 2026', cost: 680, payment: 'Paid', status: 'Completed' },
]

const initialStaff = [
  { id: 'ST-024', name: 'Priya Nair', role: 'Fleet manager', phone: '+91 98201 23456', salary: 28000, attendance: '24 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-023', name: 'Dev Patel', role: 'Operations associate', phone: '+91 98202 34567', salary: 22000, attendance: '23 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-022', name: 'Sara Khan', role: 'Customer support', phone: '+91 98203 45678', salary: 24000, attendance: '26 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-021', name: 'Nikhil Rao', role: 'Delivery associate', phone: '+91 98204 56789', salary: 19500, attendance: '—', nextSalary: '—', status: 'Inactive' },
]

const seed = {
  vehicles: initialVehicles,
  customers: initialCustomers,
  bookings: initialBookings,
  payments: initialPayments,
  documents: initialDocuments,
  maintenance: initialMaintenance,
  staff: initialStaff,
}

export function DemoDataProvider({ children }) {
  const [data, setData] = useState(seed)

  function addRecord(collection, record) {
    setData((current) => ({
      ...current,
      [collection]: [record, ...current[collection]],
    }))
  }

  function updateRecord(collection, id, changes) {
    setData((current) => ({
      ...current,
      [collection]: current[collection].map((record) =>
        record.id === id ? { ...record, ...changes } : record,
      ),
    }))
  }

  return (
    <DemoDataContext.Provider value={{ ...data, addRecord, updateRecord }}>
      {children}
    </DemoDataContext.Provider>
  )
}

export function useDemoData() {
  const context = useContext(DemoDataContext)
  if (!context) {
    throw new Error('useDemoData must be used within DemoDataProvider.')
  }
  return context
}
