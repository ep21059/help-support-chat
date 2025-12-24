<script setup>
import { ref, computed } from 'vue';
import ChatWidget from './components/ChatWidget.vue';
import AdminDashboard from './components/AdminDashboard.vue';

// デモ用の簡易ハッシュルーティング
const currentRoute = ref(window.location.hash);

window.addEventListener('hashchange', () => {
  currentRoute.value = window.location.hash;
});

const isAdmin = computed(() => {
    return currentRoute.value === '#admin';
});
</script>

<template>
  <div class="min-h-screen bg-transparent">
    <!-- 管理画面 -->
    <AdminDashboard v-if="isAdmin" />
    
    <!-- 訪問者画面 (デフォルト) -->
    <div v-else>
      <div class="p-8 max-w-2xl mx-auto mt-20 text-center">
          <h1 class="text-4xl font-bold mb-4 text-gray-800">ようこそ</h1>
          <p class="text-lg text-gray-600 mb-8">これはチャットシステムのデモ用ページです。画面の右下にチャットウィジェットが表示されています。</p>
          <div class="p-4 bg-blue-50 border border-blue-100 rounded text-sm text-blue-800 inline-block">
              管理者用ダッシュボードを表示するには、URLの末尾に <a href="#admin" class="font-bold underline">#admin</a> を追加してください。
          </div>
      </div>
      <ChatWidget />
    </div>
  </div>
</template>
