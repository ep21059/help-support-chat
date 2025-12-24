<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { v4 as uuidv4 } from 'uuid';
import { MessageCircle, X, Send, Image as ImageIcon } from 'lucide-vue-next';

const isOpen = ref(false);
const messages = ref([]);
const newMessage = ref('');
const visitorId = ref('');
let socket = null;
const messagesContainer = ref(null);
const fileInput = ref(null);

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = API_URL.replace('http', 'ws');

onMounted(async () => {
  const savedId = localStorage.getItem('chat_visitor_id');
  if (savedId) {
    visitorId.value = savedId;
  } else {
    visitorId.value = uuidv4();
    localStorage.setItem('chat_visitor_id', visitorId.value);
  }

  await fetchHistory();
  connectWebSocket();
});

const connectWebSocket = () => {
    socket = new WebSocket(`${WS_URL}/api/ws/visitor/${visitorId.value}`);
    
    // 1. 接続確立
    socket.onopen = () => {
        console.log("Connected to Chat WS");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'messages_read') {
            // 既読イベントの処理
            if (data.reader_type === 'operator') {
                messages.value.forEach(msg => {
                    if (msg.sender_type === 'visitor') {
                        msg.is_read = true;
                    }
                });
            }
        } else {
            // 通常メッセージ受信と追加
            messages.value.push(data);
            scrollToBottom();
            
            // チャットが開いていて、相手からのメッセージなら既読にする
            if (isOpen.value && data.sender_type !== 'visitor') {
                markAsRead();
            }
        }
    };
    
    socket.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };
};

const fetchHistory = async () => {
    try {
        const res = await fetch(`${API_URL}/api/conversations/${visitorId.value}`);
        if(res.ok) {
            const data = await res.json();
             messages.value = data.messages || [];
             scrollToBottom();
        }
    } catch (e) {
        console.log("No history found or error", e);
    }
};

const sendMessage = () => {
    if (!newMessage.value.trim() || !socket) return;
    
    // 3. メッセージ送信
    const payload = { content: newMessage.value };
    socket.send(JSON.stringify(payload));
    newMessage.value = '';
};

const triggerFileUpload = () => {
    fileInput.value.click();
};

const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.url) {
            const payload = {
                image_url: data.url,
                content: "" // 画像のみの場合
            };
            socket.send(JSON.stringify(payload));
        }
    } catch (e) {
        console.error("Upload failed", e);
    }
};

const scrollToBottom = () => {
    nextTick(() => {
        if (messagesContainer.value) {
            messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
        }
    });
};

const markAsRead = async () => {
    try {
        await fetch(`${API_URL}/api/conversations/${visitorId.value}/read`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ sender_type: 'visitor' })
        });
    } catch (e) {
        console.error("Failed to mark read", e);
    }
};

const toggleChat = () => {
    isOpen.value = !isOpen.value;
    if(isOpen.value) {
        scrollToBottom();
        markAsRead();
    }
};
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col items-end">
    <div v-if="isOpen" class="bg-white w-80 h-96 rounded-xl shadow-2xl flex flex-col overflow-hidden mb-4 border border-gray-100 animate-fade-in-up">
      <div class="bg-gradient-to-r from-blue-600 to-indigo-600 p-4 text-white flex justify-between items-center shadow-md">
        <div>
           <h3 class="font-bold text-sm">サポートチーム</h3>
           <p class="text-xs text-blue-100">通常、数分以内に返信します。</p>
        </div>
        <button @click="toggleChat" class="hover:bg-white/20 p-1 rounded transition-colors">
          <X size="18" />
        </button>
      </div>
      
      <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50/50">
        <div v-if="messages.length === 0" class="text-center text-gray-400 text-xs mt-10">
            お問い合わせありがとうございます。
        </div>
        <div v-for="msg in messages" :key="msg.id" 
             class="flex flex-col text-sm max-w-[85%]"
             :class="msg.sender_type === 'visitor' ? 'self-end items-end' : 'self-start items-start'">
           <div :class="['px-3 py-2 rounded-2xl shadow-sm', 
                      msg.sender_type === 'visitor' ? 'bg-blue-600 text-white rounded-br-none' : 
                      msg.sender_type === 'bot' ? 'bg-indigo-50 text-indigo-900 border border-indigo-100 rounded-bl-none' :
                      'bg-white text-gray-800 border border-gray-100 rounded-bl-none']">
               <div v-if="msg.image_url">
                   <img :src="`${API_URL}${msg.image_url}`" class="max-w-[200px] rounded-lg mb-1" />
               </div>
               <span v-if="msg.content">{{ msg.content }}</span>
           </div>
            <span class="text-[10px] text-gray-400 mt-1 px-1 flex gap-1 items-center">
                <span v-if="msg.sender_type === 'bot'">🤖</span>
                <span v-if="msg.sender_type === 'visitor' && msg.is_read" class="text-blue-500 font-bold">既読</span>
                {{ new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}
            </span>
        </div>
      </div>
      
      <div class="p-3 border-t border-gray-100 bg-white flex items-center gap-2">
        <input type="file" ref="fileInput" @change="handleFileUpload" accept="image/*" class="hidden" />
        <button @click="triggerFileUpload" class="p-2 text-gray-400 hover:text-blue-600 transition-colors">
            <ImageIcon size="20" />
        </button>
        <input v-model="newMessage" @keyup.enter="sendMessage" 
               type="text" placeholder="メッセージを入力してください" 
               class="flex-1 bg-gray-100 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all" />
        <button @click="sendMessage" class="bg-blue-600 text-white p-2 rounded-full hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50" :disabled="!newMessage.trim()">
          <Send size="16" />
        </button>
      </div>
    </div>

    <button @click="toggleChat" 
            class="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-4 shadow-xl transition-all hover:scale-110 active:scale-95">
      <MessageCircle v-if="!isOpen" size="28" />
      <X v-else size="28" />
    </button>
  </div>
</template>

<style scoped>
.animate-fade-in-up {
    animation: fadeInUp 0.3s ease-out;
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
