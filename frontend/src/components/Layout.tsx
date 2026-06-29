import React from 'react';
import { BarChart3, LayoutDashboard, LogOut, MessageCircle, MessageSquare, Package, ShoppingCart, User } from 'lucide-react';

interface NavItem { icon: React.ReactNode; label: string; path: string; }

const navItems: NavItem[] = [
  { icon: React.createElement(LayoutDashboard), label: '仪表盘', path: '/dashboard' },
  { icon: React.createElement(User), label: '账号管理', path: '/accounts' },
  { icon: React.createElement(Package), label: '商品管理', path: '/items' },
  { icon: React.createElement(MessageSquare), label: '自动回复', path: '/keywords' },
  { icon: React.createElement(MessageCircle), label: '确认收货', path: '/confirm-receipt' },
  { icon: React.createElement(ShoppingCart), label: '订单管理', path: '/orders' },
  { icon: React.createElement(BarChart3), label: '数据统计', path: '/statistics' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const path = window.location.pathname;

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.href = '/login';
  };

  return (
    <div style={{ display: 'flex' }}>
      <div className='sidebar'>
        <div style={{ padding: '20px 20px 12px', fontSize: 18, fontWeight: 700, color: '#2d5a8a' }}>
          🐟 闲鱼助手
        </div>
        {navItems.map((item) => (
          <a key={item.path} href={item.path} className={'sidebar-item' + (path.startsWith(item.path) ? ' active' : '')}>
            {item.icon}
            <span>{item.label}</span>
          </a>
        ))}
        <div style={{ marginTop: 'auto', padding: '20px' }}>
          <a href='#' onClick={(e) => { e.preventDefault(); handleLogout(); }} className='sidebar-item' style={{ color: '#b8860b' }}>
            {React.createElement(LogOut)}
            <span>退出登录</span>
          </a>
        </div>
      </div>
      <div className='main-content'>
        {children}
      </div>
    </div>
  );
}
