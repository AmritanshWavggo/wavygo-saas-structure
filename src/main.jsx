import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import QueryProvider from './providers/QueryProvider.jsx'
import { AuthProvider } from './providers/AuthProvider.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryProvider><AuthProvider><App /></AuthProvider></QueryProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
