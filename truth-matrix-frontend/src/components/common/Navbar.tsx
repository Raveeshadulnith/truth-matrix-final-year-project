import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheckIcon,
  MenuIcon,
  XIcon,
  UserIcon,
  LogOutIcon,
  SettingsIcon,
  LayoutDashboardIcon,
  HistoryIcon,
  ScanIcon } from
'lucide-react';
import { Button } from './Button';
import { ThemeToggle } from './ThemeToggle';
import { useAuthStore } from '../../store/authStore';
import { ROUTES, NAV_LINKS } from '../../utils/constants';
export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuthStore();
  const visibleNavLinks = NAV_LINKS.filter((link) => {
    if (link.label === 'About' && !isAuthenticated) {
      return false;
    }

    return !link.protected || isAuthenticated;
  });
  const handleLogout = () => {
    logout();
    navigate(ROUTES.HOME);
    setUserMenuOpen(false);
  };
  const isActive = (path: string) => location.pathname === path;
  return (
    <nav className="sticky top-0 z-40 w-full glass border-b border-gray-200/50 dark:border-navy-700/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to={ROUTES.HOME} className="flex items-center gap-2 group">
            <div className="relative">
              <ShieldCheckIcon className="w-8 h-8 text-neon-cyan transition-all duration-300 group-hover:text-neon-violet" />
              <div className="absolute inset-0 blur-lg bg-neon-cyan/30 group-hover:bg-neon-violet/30 transition-all duration-300" />
            </div>
            <span className="text-xl font-bold gradient-text">
              TruthMatrix
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {visibleNavLinks.map((link) =>
              <Link
                key={link.href}
                to={link.href}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                  ${isActive(link.href) ? 'text-neon-cyan bg-neon-cyan/10' : 'text-gray-600 dark:text-gray-300 hover:text-neon-cyan hover:bg-neon-cyan/5'}
                `}>

                  {link.label}
                </Link>

            )}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            <ThemeToggle />

            {isAuthenticated ?
            <div className="relative">
                <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-navy-800 transition-colors">

                  {user?.profilePicture ?
                <img
                  src={user.profilePicture}
                  alt={user.fullName}
                  className="w-8 h-8 rounded-full object-cover ring-2 ring-neon-cyan/50" /> :


                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center">
                      <UserIcon className="w-4 h-4 text-white" />
                    </div>
                }
                  <span className="hidden sm:block text-sm font-medium text-gray-700 dark:text-gray-300">
                    {user?.fullName?.split(' ')[0]}
                  </span>
                </button>

                <AnimatePresence>
                  {userMenuOpen &&
                <>
                      <div
                    className="fixed inset-0 z-10"
                    onClick={() => setUserMenuOpen(false)} />

                      <motion.div
                    initial={{
                      opacity: 0,
                      y: 10,
                      scale: 0.95
                    }}
                    animate={{
                      opacity: 1,
                      y: 0,
                      scale: 1
                    }}
                    exit={{
                      opacity: 0,
                      y: 10,
                      scale: 0.95
                    }}
                    transition={{
                      duration: 0.15
                    }}
                    className="absolute right-0 mt-2 w-56 py-2 bg-white dark:bg-navy-800 rounded-xl shadow-lg border border-gray-200 dark:border-navy-700 z-20">

                        <div className="px-4 py-2 border-b border-gray-200 dark:border-navy-700">
                          <p className="text-sm font-semibold text-gray-900 dark:text-white">
                            {user?.fullName}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {user?.email}
                          </p>
                        </div>

                        <div className="py-1">
                          <Link
                        to={ROUTES.DASHBOARD}
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700">

                            <LayoutDashboardIcon className="w-4 h-4" />
                            Dashboard
                          </Link>
                          <Link
                        to={ROUTES.ANALYZE}
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700">

                            <ScanIcon className="w-4 h-4" />
                            Analyze
                          </Link>
                          <Link
                        to={ROUTES.HISTORY}
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700">

                            <HistoryIcon className="w-4 h-4" />
                            History
                          </Link>
                          <Link
                        to={ROUTES.SETTINGS}
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700">

                            <SettingsIcon className="w-4 h-4" />
                            Settings
                          </Link>
                        </div>

                        <div className="border-t border-gray-200 dark:border-navy-700 pt-1">
                          <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">

                            <LogOutIcon className="w-4 h-4" />
                            Sign Out
                          </button>
                        </div>
                      </motion.div>
                    </>
                }
                </AnimatePresence>
              </div> :

            <div className="hidden sm:flex items-center gap-2">
                <Button variant="ghost" onClick={() => navigate(ROUTES.LOGIN)}>
                  Sign In
                </Button>
                <Button
                variant="primary"
                onClick={() => navigate(ROUTES.REGISTER)}>

                  Get Started
                </Button>
              </div>
            }

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-800">

              {mobileMenuOpen ?
              <XIcon className="w-6 h-6" /> :

              <MenuIcon className="w-6 h-6" />
              }
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen &&
        <motion.div
          initial={{
            opacity: 0,
            height: 0
          }}
          animate={{
            opacity: 1,
            height: 'auto'
          }}
          exit={{
            opacity: 0,
            height: 0
          }}
          className="md:hidden border-t border-gray-200 dark:border-navy-700 bg-white dark:bg-navy-900">

            <div className="px-4 py-4 space-y-2">
              {visibleNavLinks.map((link) =>
            <Link
              key={link.href}
              to={link.href}
              onClick={() => setMobileMenuOpen(false)}
              className={`
                    block px-4 py-3 rounded-lg text-base font-medium transition-colors
                    ${isActive(link.href) ? 'text-neon-cyan bg-neon-cyan/10' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-800'}
                  `}>

                  {link.label}
                </Link>
            )}

              {!isAuthenticated &&
            <div className="pt-4 space-y-2 border-t border-gray-200 dark:border-navy-700">
                  <Button
                variant="ghost"
                className="w-full"
                onClick={() => {
                  navigate(ROUTES.LOGIN);
                  setMobileMenuOpen(false);
                }}>

                    Sign In
                  </Button>
                  <Button
                variant="primary"
                className="w-full"
                onClick={() => {
                  navigate(ROUTES.REGISTER);
                  setMobileMenuOpen(false);
                }}>

                    Get Started
                  </Button>
                </div>
            }
            </div>
          </motion.div>
        }
      </AnimatePresence>
    </nav>);

}
