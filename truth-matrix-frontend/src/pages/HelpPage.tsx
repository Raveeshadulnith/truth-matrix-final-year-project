import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ChevronDownIcon,
  MessageCircleIcon,
  MailIcon,
  FileTextIcon } from
'lucide-react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { FAQ_ITEMS } from '../utils/constants';
export function HelpPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-12">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            How can we help?
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            Find answers to common questions or reach out to our support team.
          </p>
        </div>

        {/* Quick Links */}
        <div className="grid sm:grid-cols-3 gap-6">
          <Card
            variant="glass"
            hover
            className="p-6 text-center cursor-pointer">

            <FileTextIcon className="w-8 h-8 text-neon-cyan mx-auto mb-3" />
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Documentation
            </h3>
            <p className="text-sm text-gray-500 mt-1">Read our guides</p>
          </Card>
          <Card
            variant="glass"
            hover
            className="p-6 text-center cursor-pointer">

            <MessageCircleIcon className="w-8 h-8 text-neon-violet mx-auto mb-3" />
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Live Chat
            </h3>
            <p className="text-sm text-gray-500 mt-1">Talk to an expert</p>
          </Card>
          <Card
            variant="glass"
            hover
            className="p-6 text-center cursor-pointer">

            <MailIcon className="w-8 h-8 text-neon-pink mx-auto mb-3" />
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Email Support
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              support@deepguardian.ai
            </p>
          </Card>
        </div>

        {/* FAQ */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {FAQ_ITEMS.map((item, index) =>
            <Card key={index} variant="default" className="overflow-hidden">
                <button
                className="w-full px-6 py-4 flex items-center justify-between text-left focus:outline-none"
                onClick={() => setOpenFaq(openFaq === index ? null : index)}>

                  <span className="font-medium text-gray-900 dark:text-white">
                    {item.question}
                  </span>
                  <ChevronDownIcon
                  className={`w-5 h-5 text-gray-500 transition-transform ${openFaq === index ? 'rotate-180' : ''}`} />

                </button>
                <motion.div
                initial={false}
                animate={{
                  height: openFaq === index ? 'auto' : 0
                }}
                className="overflow-hidden">

                  <div className="px-6 pb-4 text-gray-600 dark:text-gray-400 border-t border-gray-100 dark:border-navy-700 pt-4">
                    {item.answer}
                  </div>
                </motion.div>
              </Card>
            )}
          </div>
        </div>

        {/* Contact Form CTA */}
        <Card
          variant="glass"
          className="bg-gradient-to-br from-navy-800 to-navy-900 border-neon-cyan/30">

          <div className="p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-4">
              Still need help?
            </h2>
            <p className="text-gray-300 mb-6">
              Our support team is available 24/7 to assist you with any
              technical issues or questions.
            </p>
            <Button variant="primary">Contact Support</Button>
          </div>
        </Card>
      </div>
    </div>);

}
