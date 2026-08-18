import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  SearchIcon,
  GridIcon,
  ListIcon,
  TrashIcon,
  DownloadIcon,
  ImageIcon,
  VideoIcon,
  MusicIcon,
  CheckIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { useAnalysisStore, type Analysis } from '../store/analysisStore';
import { ROUTES } from '../utils/constants';
import {
  formatRelativeTime,
  formatFileSize,
  truncateFilename } from
'../utils/formatters';
export function HistoryPage() {
  const navigate = useNavigate();
  const { analyses, setCurrentAnalysis, deleteAnalysis } =
  useAnalysisStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterResult, setFilterResult] = useState<'all' | 'fake' | 'real'>(
    'all'
  );
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const filteredAnalyses = analyses.filter((analysis) => {
    const matchesSearch = analysis.filename.
    toLowerCase().
    includes(searchQuery.toLowerCase());
    const matchesFilter =
    filterResult === 'all' || analysis.result === filterResult;
    return matchesSearch && matchesFilter;
  });
  const handleViewResult = (analysis: Analysis) => {
    setCurrentAnalysis(analysis);
    navigate(ROUTES.RESULTS);
  };
  const handleDelete = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm('Are you sure you want to delete this analysis?')) {
      deleteAnalysis(id);
    }
  };
  const handleBulkDelete = () => {
    if (confirm(`Delete ${selectedItems.length} selected items?`)) {
      selectedItems.forEach((id) => deleteAnalysis(id));
      setSelectedItems([]);
    }
  };
  const handleExport = () => {
    const csv = [
    ['Filename', 'Type', 'Result', 'Confidence', 'Date'].join(','),
    ...filteredAnalyses.map((a) =>
    [a.filename, a.fileType, a.result, a.confidence, a.createdAt].join(',')
    )].
    join('\n');
    const blob = new Blob([csv], {
      type: 'text/csv'
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'deepguardian-history.csv';
    link.click();
  };
  const getFileIcon = (type: string) => {
    if (type === 'video') return VideoIcon;
    if (type === 'audio') return MusicIcon;
    return ImageIcon;
  };
  const toggleSelect = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedItems((prev) =>
    prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">

          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
              Analysis History
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {analyses.length} total analyses
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              leftIcon={<DownloadIcon className="w-4 h-4" />}
              onClick={handleExport}
              disabled={filteredAnalyses.length === 0}>

              Export CSV
            </Button>
            {selectedItems.length > 0 &&
            <Button
              variant="danger"
              leftIcon={<TrashIcon className="w-4 h-4" />}
              onClick={handleBulkDelete}>

                Delete ({selectedItems.length})
              </Button>
            }
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          transition={{
            delay: 0.1
          }}
          className="flex flex-col sm:flex-row gap-4 mb-6">

          <div className="flex-1">
            <Input
              placeholder="Search by filename..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<SearchIcon className="w-5 h-5" />} />

          </div>
          <div className="flex items-center gap-2">
            {/* Filter Dropdown */}
            <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-navy-800 rounded-xl">
              {(['all', 'fake', 'real'] as const).map((filter) =>
              <button
                key={filter}
                onClick={() => setFilterResult(filter)}
                className={`
                    px-3 py-2 rounded-lg text-sm font-medium transition-all capitalize
                    ${filterResult === filter ? 'bg-white dark:bg-navy-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}
                  `}>

                  {filter}
                </button>
              )}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-navy-800 rounded-xl">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-white dark:bg-navy-700 text-neon-cyan shadow-sm' : 'text-gray-500 dark:text-gray-400'}`}>

                <GridIcon className="w-5 h-5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-lg transition-all ${viewMode === 'list' ? 'bg-white dark:bg-navy-700 text-neon-cyan shadow-sm' : 'text-gray-500 dark:text-gray-400'}`}>

                <ListIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </motion.div>

        {/* Results */}
        {filteredAnalyses.length === 0 ?
        <motion.div
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          className="text-center py-16">

            <div className="w-20 h-20 mx-auto rounded-2xl bg-gray-100 dark:bg-navy-800 flex items-center justify-center mb-4">
              <ImageIcon className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              No analyses found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchQuery || filterResult !== 'all' ?
            'Try adjusting your search or filters' :
            'Start by analyzing your first image or video'}
            </p>
            <Link to={ROUTES.ANALYZE}>
              <Button variant="primary">Start Analyzing</Button>
            </Link>
          </motion.div> :
        viewMode === 'grid' ?
        <motion.div
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">

            <AnimatePresence>
              {filteredAnalyses.map((analysis, index) => {
              const isFake = analysis.result === 'fake';
              const isSelected = selectedItems.includes(analysis.id);
              const FileIcon = getFileIcon(analysis.fileType);
              return (
                <motion.div
                  key={analysis.id}
                  layout
                  initial={{
                    opacity: 0,
                    scale: 0.9
                  }}
                  animate={{
                    opacity: 1,
                    scale: 1
                  }}
                  exit={{
                    opacity: 0,
                    scale: 0.9
                  }}
                  transition={{
                    delay: index * 0.05
                  }}>

                    <Card
                    variant="default"
                    hover
                    className={`relative h-full ${isSelected ? 'ring-2 ring-neon-cyan' : ''}`}
                    onClick={() => handleViewResult(analysis)}>

                      {/* Selection Checkbox */}
                      <button
                      onClick={(e) => toggleSelect(analysis.id, e)}
                      className={`absolute top-3 left-3 z-10 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-colors ${isSelected ? 'bg-neon-cyan border-neon-cyan' : 'bg-black/20 border-white/50 hover:border-white'}`}>

                        {isSelected &&
                      <CheckIcon className="w-4 h-4 text-white" />
                      }
                      </button>

                      {/* Delete Button */}
                      <button
                      onClick={(e) => handleDelete(analysis.id, e)}
                      className="absolute top-3 right-3 z-10 p-1.5 rounded-md bg-black/20 text-white/70 hover:text-white hover:bg-black/40 transition-colors">

                        <TrashIcon className="w-4 h-4" />
                      </button>

                      {/* Thumbnail */}
                      <div className="relative aspect-video bg-gray-100 dark:bg-navy-900 overflow-hidden">
                        {analysis.thumbnailUrl ?
                      <img
                        src={analysis.thumbnailUrl}
                        alt={analysis.filename}
                        className="w-full h-full object-cover" /> :


                      <div className="w-full h-full flex items-center justify-center">
                            <FileIcon className="w-12 h-12 text-gray-400" />
                          </div>
                      }
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
                          <Badge
                          variant={isFake ? 'danger' : 'success'}
                          size="sm">

                            {isFake ? 'DEEPFAKE' : 'AUTHENTIC'}
                          </Badge>
                          <span className="text-white text-sm font-bold">
                            {analysis.confidence.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {/* Info */}
                      <div className="p-4">
                        <p className="font-medium text-gray-900 dark:text-white truncate mb-1">
                          {analysis.filename}
                        </p>
                        <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                          <span>{formatRelativeTime(analysis.createdAt)}</span>
                          <span className="capitalize">
                            {analysis.fileType}
                          </span>
                        </div>
                      </div>
                    </Card>
                  </motion.div>);

            })}
            </AnimatePresence>
          </motion.div> :

        <motion.div
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          className="rounded-2xl bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700 overflow-hidden">

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-navy-700 bg-gray-50 dark:bg-navy-900/50">
                    <th className="px-6 py-4 text-sm font-semibold text-gray-900 dark:text-white">
                      File
                    </th>
                    <th className="px-6 py-4 text-sm font-semibold text-gray-900 dark:text-white">
                      Result
                    </th>
                    <th className="px-6 py-4 text-sm font-semibold text-gray-900 dark:text-white">
                      Confidence
                    </th>
                    <th className="px-6 py-4 text-sm font-semibold text-gray-900 dark:text-white">
                      Date
                    </th>
                    <th className="px-6 py-4 text-right text-sm font-semibold text-gray-900 dark:text-white">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-navy-700">
                  <AnimatePresence>
                    {filteredAnalyses.map((analysis) => {
                    const isFake = analysis.result === 'fake';
                    const isSelected = selectedItems.includes(analysis.id);
                    const FileIcon = getFileIcon(analysis.fileType);
                    return (
                      <motion.tr
                        key={analysis.id}
                        layout
                        initial={{
                          opacity: 0
                        }}
                        animate={{
                          opacity: 1
                        }}
                        exit={{
                          opacity: 0
                        }}
                        className={`hover:bg-gray-50 dark:hover:bg-navy-700/50 transition-colors cursor-pointer ${isSelected ? 'bg-neon-cyan/5 dark:bg-neon-cyan/10' : ''}`}
                        onClick={() => handleViewResult(analysis)}>

                          <td className="px-6 py-4">
                            <div className="flex items-center gap-4">
                              <button
                              onClick={(e) => toggleSelect(analysis.id, e)}
                              className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${isSelected ? 'bg-neon-cyan border-neon-cyan' : 'border-gray-300 dark:border-navy-600'}`}>

                                {isSelected &&
                              <CheckIcon className="w-3 h-3 text-white" />
                              }
                              </button>
                              <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-navy-700 flex items-center justify-center flex-shrink-0 overflow-hidden">
                                {analysis.thumbnailUrl ?
                              <img
                                src={analysis.thumbnailUrl}
                                alt=""
                                className="w-full h-full object-cover" /> :


                              <FileIcon className="w-5 h-5 text-gray-400" />
                              }
                              </div>
                              <div>
                                <p className="font-medium text-gray-900 dark:text-white">
                                  {truncateFilename(analysis.filename, 30)}
                                </p>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                  {formatFileSize(analysis.fileSize)}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <Badge
                            variant={isFake ? 'danger' : 'success'}
                            size="sm">

                              {isFake ? 'DEEPFAKE' : 'AUTHENTIC'}
                            </Badge>
                          </td>
                          <td className="px-6 py-4">
                            <span
                            className={`font-semibold ${isFake ? 'text-neon-red' : 'text-neon-green'}`}>

                              {analysis.confidence.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                            {formatRelativeTime(analysis.createdAt)}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <button
                            onClick={(e) => handleDelete(analysis.id, e)}
                            className="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">

                              <TrashIcon className="w-5 h-5" />
                            </button>
                          </td>
                        </motion.tr>);

                  })}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          </motion.div>
        }
      </div>
    </div>);

}
