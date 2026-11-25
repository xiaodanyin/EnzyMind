import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/results/:id?',
    name: 'Results',
    component: () => import('@/views/Results.vue'),
    meta: { title: 'Research Results' }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/agent',
    name: 'Agent',
    component: () => import('@/views/Agent.vue'),
    meta: { title: 'AI Agent' }
  },
  // Prediction routes
  {
    path: '/predict/enzyme',
    name: 'EnzymeRecognition',
    component: () => import('@/views/predict/EnzymeRecognition.vue'),
    meta: { title: 'Enzyme Recognition', category: 'prediction' }
  },
  {
    path: '/predict/ec',
    name: 'ECPrediction',
    component: () => import('@/views/predict/ECPrediction.vue'),
    meta: { title: 'EC Number Prediction', category: 'prediction' }
  },
  {
    path: '/predict/substrate',
    name: 'SubstratePrediction',
    component: () => import('@/views/predict/SubstratePrediction.vue'),
    meta: { title: 'Substrate Determination', category: 'prediction' }
  },
  {
    path: '/predict/kcat',
    name: 'KcatPrediction',
    component: () => import('@/views/predict/KcatPrediction.vue'),
    meta: { title: 'Kcat Prediction', category: 'prediction' }
  },
  {
    path: '/predict/km',
    name: 'KmPrediction',
    component: () => import('@/views/predict/KmPrediction.vue'),
    meta: { title: 'Km Prediction', category: 'prediction' }
  },
  {
    path: '/predict/activesite',
    name: 'ActiveSitePrediction',
    component: () => import('@/views/predict/ActiveSitePrediction.vue'),
    meta: { title: 'Active Site Prediction', category: 'prediction' }
  },
  {
    path: '/predict/recommendation',
    name: 'EnzymeRecommendation',
    component: () => import('@/views/predict/EnzymeRecommendation.vue'),
    meta: { title: 'Enzyme Recommendation', category: 'prediction' }
  },
  // Utility routes
  {
    path: '/utility/enzyme-info',
    name: 'EnzymeInfo',
    component: () => import('@/views/utility/EnzymeInfo.vue'),
    meta: { title: 'Enzyme Information', category: 'utility' }
  },
  {
    path: '/utility/structure',
    name: 'StructurePrediction',
    component: () => import('@/views/utility/StructurePrediction.vue'),
    meta: { title: 'Structure Prediction', category: 'utility' }
  },
  {
    path: '/utility/alignment',
    name: 'SequenceAlignment',
    component: () => import('@/views/utility/SequenceAlignment.vue'),
    meta: { title: 'Sequence Alignment', category: 'utility' }
  },
  {
    path: '/utility/parameters',
    name: 'ProteinParameters',
    component: () => import('@/views/utility/ProteinParameters.vue'),
    meta: { title: 'Protein Parameters', category: 'utility' }
  },
  // Help
  {
    path: '/help',
    name: 'Help',
    component: () => import('@/views/Help.vue'),
    meta: { title: 'Help' }
  },
]

const router = createRouter({
  history: createWebHistory('/enzymind'),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  },
})

// Update document title
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - EnzyMind` : 'EnzyMind'
  next()
})

export default router
