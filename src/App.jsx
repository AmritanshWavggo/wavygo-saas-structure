import { Navigate, Route, Routes } from 'react-router-dom'
import { DemoDataProvider } from './data/DemoDataContext.jsx'
import VendorLayout from './layouts/VendorLayout.jsx'
import LoginPage from './pages/Login.jsx'
import Dashboard from './pages/Dashboard/Dashboard.jsx'
import Vehicles from './pages/Vehicles/Vehicles.jsx'
import AddVehicle from './pages/Vehicles/AddVehicle.jsx'
import Bookings from './pages/Bookings/Bookings.jsx'
import AddBooking from './pages/Bookings/AddBooking.jsx'
import Customers from './pages/Customers/Customers.jsx'
import Payments from './pages/Payments/Payments.jsx'
import Documents from './pages/Documents/Documents.jsx'
import Maintenance from './pages/Maintenance/Maintenance.jsx'
import Staff from './pages/Staff/Staff.jsx'
import Reports from './pages/Reports/Reports.jsx'
import Settings from './pages/Settings/Settings.jsx'

function App() {
  return (
    <DemoDataProvider>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<VendorLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="vehicles" element={<Vehicles />} />
          <Route path="vehicles/new" element={<AddVehicle />} />
          <Route path="bookings" element={<Bookings />} />
          <Route path="bookings/new" element={<AddBooking />} />
          <Route path="customers" element={<Customers />} />
          <Route path="payments" element={<Payments />} />
          <Route path="documents" element={<Documents />} />
          <Route path="maintenance" element={<Maintenance />} />
          <Route path="staff" element={<Staff />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </DemoDataProvider>
  )
}

export default App
