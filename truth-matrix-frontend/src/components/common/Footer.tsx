import { Link } from 'react-router-dom';
import {
  ShieldCheckIcon,
  GithubIcon,
  TwitterIcon,
  LinkedinIcon,
  MailIcon } from
'lucide-react';
import { ROUTES } from '../../utils/constants';
export function Footer() {
  const currentYear = new Date().getFullYear();
  const footerLinks = {
    Product: [
    {
      label: 'Features',
      href: ROUTES.ABOUT
    },
    {
      label: 'API Docs',
      href: ROUTES.API_DOCS
    },
    {
      label: 'Browser Extension',
      href: '#'
    }],

    Company: [
    {
      label: 'About',
      href: ROUTES.ABOUT
    },
    {
      label: 'Blog',
      href: '#'
    },
    {
      label: 'Careers',
      href: '#'
    },
    {
      label: 'Contact',
      href: ROUTES.HELP
    }],

    Resources: [
    {
      label: 'Help Center',
      href: ROUTES.HELP
    },
    {
      label: 'Documentation',
      href: ROUTES.API_DOCS
    },
    {
      label: 'Research',
      href: '#'
    },
    {
      label: 'Status',
      href: '#'
    }],

    Legal: [
    {
      label: 'Privacy Policy',
      href: '#'
    },
    {
      label: 'Terms of Service',
      href: '#'
    },
    {
      label: 'Cookie Policy',
      href: '#'
    },
    {
      label: 'GDPR',
      href: '#'
    }]

  };
  const socialLinks = [
  {
    icon: GithubIcon,
    href: 'https://github.com',
    label: 'GitHub'
  },
  {
    icon: TwitterIcon,
    href: 'https://twitter.com',
    label: 'Twitter'
  },
  {
    icon: LinkedinIcon,
    href: 'https://linkedin.com',
    label: 'LinkedIn'
  },
  {
    icon: MailIcon,
    href: 'mailto:hello@deepguardian.ai',
    label: 'Email'
  }];

  return (
    <footer className="w-full bg-gray-50 dark:bg-navy-900 border-t border-gray-200 dark:border-navy-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          {/* Brand */}
          <div className="col-span-2">
            <Link to={ROUTES.HOME} className="flex items-center gap-2 mb-4">
              <ShieldCheckIcon className="w-8 h-8 text-neon-cyan" />
              <span className="text-xl font-bold gradient-text">
                TruthMatrix
              </span>
            </Link>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 max-w-xs">
              AI-powered deepfake detection with explainable heatmaps. Protect
              truth in the digital age.
            </p>
            <div className="flex items-center gap-3">
              {socialLinks.map((social) =>
              <a
                key={social.label}
                href={social.href}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 rounded-lg text-gray-400 hover:text-neon-cyan hover:bg-neon-cyan/10 transition-colors"
                aria-label={social.label}>

                  <social.icon className="w-5 h-5" />
                </a>
              )}
            </div>
          </div>

          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) =>
          <div key={category}>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                {category}
              </h3>
              <ul className="space-y-3">
                {links.map((link) =>
              <li key={link.label}>
                    <Link
                  to={link.href}
                  className="text-sm text-gray-600 dark:text-gray-400 hover:text-neon-cyan transition-colors">

                      {link.label}
                    </Link>
                  </li>
              )}
              </ul>
            </div>
          )}
        </div>

        {/* Bottom */}
        <div className="mt-12 pt-8 border-t border-gray-200 dark:border-navy-800">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              © {currentYear} TruthMatrix. All rights reserved.
            </p>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
                All systems operational
              </span>
            </div>
          </div>
        </div>
      </div>
    </footer>);

}
