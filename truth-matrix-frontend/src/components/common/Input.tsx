import React, { useState, forwardRef } from 'react';
import { EyeIcon, EyeOffIcon } from 'lucide-react';
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}
export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
  {
    label,
    error,
    helperText,
    leftIcon,
    rightIcon,
    type,
    className = '',
    ...props
  },
  ref) =>
  {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === 'password';
    return (
      <div className="w-full">
        {label &&
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            {label}
          </label>
        }
        <div className="relative">
          {leftIcon &&
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500">
              {leftIcon}
            </div>
          }
          <input
            ref={ref}
            type={isPassword && showPassword ? 'text' : type}
            className={`
              w-full px-4 py-3 rounded-xl
              bg-white dark:bg-navy-800
              border-2 border-gray-200 dark:border-navy-600
              text-gray-900 dark:text-white
              placeholder-gray-400 dark:placeholder-gray-500
              transition-all duration-200
              focus:outline-none focus:border-neon-cyan focus:ring-2 focus:ring-neon-cyan/20
              disabled:opacity-50 disabled:cursor-not-allowed
              ${leftIcon ? 'pl-11' : ''}
              ${rightIcon || isPassword ? 'pr-11' : ''}
              ${error ? 'border-neon-red focus:border-neon-red focus:ring-neon-red/20' : ''}
              ${className}
            `}
            {...props} />

          {isPassword &&
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            tabIndex={-1}>

              {showPassword ?
            <EyeOffIcon className="w-5 h-5" /> :

            <EyeIcon className="w-5 h-5" />
            }
            </button>
          }
          {rightIcon && !isPassword &&
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500">
              {rightIcon}
            </div>
          }
        </div>
        {error && <p className="mt-1.5 text-sm text-neon-red">{error}</p>}
        {helperText && !error &&
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
            {helperText}
          </p>
        }
      </div>);

  }
);
Input.displayName = 'Input';