import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import './styles/globals.css';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import Items from './pages/Items';
import Keywords from './pages/Keywords';
import ConfirmReceiptConfig from './pages/ConfirmReceiptConfig';
import Orders from './pages/Orders';
import Statistics from './pages/Statistics';
import Layout from './components/Layout';

function App() {
  const token = localStorage.getItem('token');
  if (!token) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </BrowserRouter>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Layout><Outlet /></Layout>}>
          <Route index element={<Navigate to="/dashboard" />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="items" element={<Items />} />
          <Route path="keywords" element={<Keywords />} />
          <Route path="confirm-receipt" element={<ConfirmReceiptConfig />} />
          <Route path="orders" element={<Orders />} />
          <Route path="statistics" element={<Statistics />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
