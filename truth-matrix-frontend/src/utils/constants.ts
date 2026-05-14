export const APP_NAME = 'TruthMatrix';
export const APP_TAGLINE = 'Expose the Truth Behind Every Pixel';
export const APP_DESCRIPTION =
'AI-powered deepfake detection with explainable heatmaps';

export const SUPPORTED_IMAGE_TYPES = [
'image/jpeg',
'image/png',
'image/webp'];

export const SUPPORTED_VIDEO_TYPES = [
'video/mp4',
'video/quicktime',
'video/x-msvideo',
'video/x-matroska'];

export const SUPPORTED_AUDIO_TYPES = [
'audio/mpeg',
'audio/wav',
'audio/mp3',
'audio/mp4',
'audio/x-m4a'];


export const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',
  DASHBOARD: '/dashboard',
  ANALYZE: '/analyze',
  RESULTS: '/results',
  HISTORY: '/history',
  PROFILE: '/profile',
  SETTINGS: '/settings',
  API_DOCS: '/api-docs',
  ABOUT: '/about',
  HELP: '/help',
  ADMIN: '/admin'
} as const;

export const NAV_LINKS = [
{ label: 'Dashboard', href: ROUTES.DASHBOARD, protected: true },
{ label: 'Analyze', href: ROUTES.ANALYZE, protected: true },
{ label: 'History', href: ROUTES.HISTORY, protected: true },
{ label: 'About', href: ROUTES.ABOUT, protected: false }];

export const FEATURES = [
{
  title: 'Real-time Detection',
  description:
  'Analyze images and videos with the connected EfficientNet-B4 trained checkpoints.',
  icon: 'Zap',
  eyebrow: 'Fast inference'
},
{
  title: 'XAI Heatmaps',
  description:
  'See image overlays and sampled video frame maps with Grad-CAM explainable AI visualizations.',
  icon: 'Eye',
  eyebrow: 'Visual proof'
},
{
  title: 'Browser Extension',
  description:
  'Right-click any image online to verify authenticity instantly.',
  icon: 'Globe',
  eyebrow: 'Web-ready'
},
{
  title: 'Multi-format Support',
  description: 'Supports JPG, PNG, MP4, and more formats up to 100MB.',
  icon: 'FileImage',
  eyebrow: 'Flexible uploads'
},
{
  title: 'Detailed Reports',
  description:
  'Get comprehensive analysis reports with artifact detection and confidence scores.',
  icon: 'FileText',
  eyebrow: 'Actionable results'
},
{
  title: 'Analysis History',
  description:
  'Return to previous scans, compare outcomes, and manage saved detections from one secure dashboard.',
  icon: 'History',
  eyebrow: 'Saved sessions'
}];


export const STATS = [
{ label: 'Images Analyzed', value: '2.4M+', icon: 'Image' },
{ label: 'Deepfakes Caught', value: '847K+', icon: 'ShieldAlert' },
{ label: 'Active Users', value: '125K+', icon: 'Users' },
{ label: 'Model Modes', value: 'Image + Video', icon: 'Target' }];


export const TESTIMONIALS = [
{
  name: 'Sarah Chen',
  role: 'Investigative Journalist',
  company: 'The Digital Times',
  avatar:
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face',
  content:
  'TruthMatrix has become an essential tool in our newsroom. We verify every suspicious image before publication.'
},
{
  name: 'Marcus Johnson',
  role: 'Security Analyst',
  company: 'CyberShield Inc.',
  avatar:
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face',
  content:
  'The explainable AI feature is a game-changer. We can now show clients exactly why content is flagged as fake.'
},
{
  name: 'Emily Rodriguez',
  role: 'Content Moderator',
  company: 'SocialGuard',
  avatar:
  'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face',
  content:
  'Processing thousands of images daily would be impossible without TruthMatrix. The API integration was seamless.'
}];


export const FAQ_ITEMS = [
{
  question: 'How accurate is TruthMatrix?',
  answer:
  'TruthMatrix now uses your trained EfficientNet-B4 image checkpoint and EfficientNet-B4 plus BiLSTM video checkpoint. Report final accuracy from your own validation or test dataset run.'
},
{
  question: 'What types of deepfakes can you detect?',
  answer:
  'The connected models analyze image and video manipulation signals. Audio analysis is reserved until the trained audio checkpoint is ready.'
},
{
  question: 'How does the heatmap visualization work?',
  answer:
  'We use Grad-CAM (Gradient-weighted Class Activation Mapping) to highlight image regions or sampled video frames the AI focused on when making its decision.'
},
{
  question: 'Is my uploaded content kept private?',
  answer:
  'Yes, all uploads are encrypted and automatically deleted after 24 hours unless you choose to save them to your history.'
},
{
  question: 'Can I use TruthMatrix for commercial purposes?',
  answer:
  'Yes, TruthMatrix includes commercial usage rights and API access for integration.'
},
{
  question: 'Do you offer an API?',
  answer:
  'Yes, we provide a REST API. Check our API documentation for integration guides.'
}];
