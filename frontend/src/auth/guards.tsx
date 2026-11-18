import { Navigate, Outlet } from 'react-router-dom';
import type { Role } from '../api/types';
import { Loading } from '../components/Feedback';
import { homePath, useAuth } from './AuthContext';

export function RequireRole({ roles }: { roles: Role[] }) {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/connexion" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homePath(user.role)} replace />;
  return <Outlet />;
}

export function PublicOnly() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  return user ? <Navigate to={homePath(user.role)} replace /> : <Outlet />;
}

export function HomeRedirect() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  return <Navigate to={user ? homePath(user.role) : '/bienvenue'} replace />;
}
