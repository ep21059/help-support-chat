<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import { Send, MessageSquare, AlertCircle, Image as ImageIcon } from 'lucide-vue-next';

const conversations = ref([]);
const selectedConvId = ref(null);
const newMessage = ref('');
const messagesContainer = ref(null);
const fileInput = ref(null);
let socket = null;

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = API_URL.replace('http', 'ws');

const activeConversation = computed(() => 
    conversations.value.find(c => c.id === selectedConvId.value)
);

onMounted(async () => {
    await fetchConversations();
    connectWebSocket();
});

const connectWebSocket = () => {
    socket = new WebSocket(`${WS_URL}/api/ws/operator`);
    
    // 1. 接続確立
    socket.onopen = () => console.log("Operator WS active");
    
    socket.onmessage = (event) => {
        // 2. メッセージ受信
        const data = JSON.parse(event.data);
        
        if (data.type === 'messages_read') {
             const conv = conversations.value.find(c => c.id === data.conversation_id);
             if (conv && conv.messages) {
                 // visitorが読んだ -> operatorのメッセージを既読に
                 if (data.reader_type === 'visitor') {
                     conv.messages.forEach(m => {
                         if(m.sender_type === 'operator') m.is_read = true;
                     });
                 }
             }
        } else {
            handleIncomingMessage(data);
        }
    };
    
    socket.onclose = () => {
        console.log("Operator WS closed");
        setTimeout(connectWebSocket, 3000);
    };
};

const handleIncomingMessage = (msg) => {
    const conv = conversations.value.find(c => c.id === msg.conversation_id);
    if (conv) {
        if (!conv.messages) conv.messages = [];
        // ローカルプッシュと一致する場合は重複を避ける
        if (!conv.messages.find(m => m.id === msg.id)) {
             conv.messages.push(msg);
        }
        // 3. リストの先頭へ移動
        
        // 会話を並び替え
        const idx = conversations.value.indexOf(conv);
        if (idx > 0) {
            conversations.value.splice(idx, 1);
            conversations.value.unshift(conv);
        }
    } else {
        fetchConversations();
    }
    
    // 現在開いている会話なら既読にする
    if (activeConversation.value && activeConversation.value.id === msg.conversation_id) {
        scrollToBottom();
        // 訪問者からのメッセージなら既読処理
        if (msg.sender_type === 'visitor') {
            markAsRead(msg.conversation_id, activeConversation.value.visitor_id);
        }
    }
};

const markAsRead = async (conversationId, visitorId) => {
    // ローカルの未読状態をクリア
    const conv = conversations.value.find(c => c.id === conversationId);
    if(conv && conv.messages) {
        conv.messages.forEach(m => {
            if(m.sender_type === 'visitor') m.is_read = true;
        });
    }

    try {
        await fetch(`${API_URL}/api/conversations/${visitorId}/read`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ sender_type: 'operator' })
        });
    } catch (e) {
        console.error("Failed to mark read", e);
    }
};

const fetchConversations = async () => {
    try {
        const res = await fetch(`${API_URL}/api/conversations`);
        if(res.ok) {
            conversations.value = await res.json();
            // IDが選択されていてもリフレッシュした場合、データの一貫性を確保
            if(conversations.value.length > 0 && !selectedConvId.value) {
                // 先頭を選択する？ いいえ。
            }
        }
    } catch(e) {
        console.error("Failed to fetch conversations", e);
    }
};

const selectConversation = (id) => {
    selectedConvId.value = id;
    scrollToBottom();
    
    const conv = conversations.value.find(c => c.id === id);
    if(conv) {
        markAsRead(id, conv.visitor_id);
    }
};

const sendMessage = () => {
    if (!newMessage.value.trim() || !activeConversation.value || !socket) return;
    
    const payload = {
        visitor_id: activeConversation.value.visitor_id,
        content: newMessage.value
    };
    
    socket.send(JSON.stringify(payload));
    newMessage.value = '';
};

const triggerFileUpload = () => {
    fileInput.value.click();
};

const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file || !activeConversation.value) return;

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
                visitor_id: activeConversation.value.visitor_id,
                image_url: data.url,
                content: "" 
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
</script>

<template>
  <div class="flex h-screen bg-gray-50 font-sans">
    <!-- サイドバー -->
    <div class="w-80 bg-white border-r border-gray-200 flex flex-col shadow-sm z-10">
      <div class="p-6 border-b border-gray-100">
        <h1 class="font-bold text-xl text-gray-800 flex items-center gap-2">
            <MessageSquare class="text-blue-600" />
            お問い合わせ受信箱
        </h1>
      </div>
      <div class="flex-1 overflow-y-auto">
         <div v-if="conversations.length === 0" class="p-6 text-center text-gray-400 text-sm">
            No active conversations.
         </div>
         <div v-for="conv in conversations" :key="conv.id"
              @click="selectConversation(conv.id)"
              :class="['p-4 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-colors', 
                       selectedConvId === conv.id ? 'bg-blue-50 border-l-4 border-blue-600 pl-3' : 'border-l-4 border-transparent']">
            <div class="flex justify-between items-start mb-1">
                <span class="font-semibold text-sm text-gray-800 truncate flex items-center gap-2">
                    Visitor {{ conv.visitor_id.slice(0,6) }}
                    <span v-if="conv.messages?.some(m => m.sender_type === 'visitor' && !m.is_read)" class="w-2 h-2 rounded-full bg-red-500"></span>
                </span>
                <span class="text-[10px] text-gray-400">{{ conv.messages?.length ? new Date(conv.messages[conv.messages.length-1].created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '' }}</span>
            </div>
            <div class="text-xs text-gray-500 truncate h-4">
                {{ conv.messages && conv.messages.length ? conv.messages[conv.messages.length - 1].content : 'New conversation' }}
            </div>
         </div>
      </div>
    </div>

    <!-- メインチャットエリア -->
    <div class="flex-1 flex flex-col bg-slate-50 relative">
        <div v-if="!activeConversation" class="m-auto text-gray-300 flex flex-col items-center">
            <MessageSquare size="64" class="mb-4 stroke-1" />
            <p class="text-lg font-light">Select a conversation to start chatting</p>
        </div>
        
        <template v-else>
            <div class="p-4 bg-white border-b border-gray-200 flex justify-between items-center shadow-sm z-10">
                <div>
                     <h2 class="font-bold text-gray-800 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-green-500"></span>
                        Visitor {{ activeConversation.visitor_id }}
                     </h2>
                     <p class="text-xs text-gray-400 ml-4 font-mono">{{ activeConversation.visitor_id }}</p>
                </div>
            </div>
            
            <div ref="messagesContainer" class="flex-1 overflow-y-auto p-8 space-y-6">
                <div v-for="msg in activeConversation.messages" :key="msg.id"
                     :class="['flex w-full', msg.sender_type === 'operator' ? 'justify-end' : 'justify-start']">
                     <div class="flex flex-col max-w-[60%]">
                        <div :class="['px-4 py-3 rounded-2xl shadow-sm text-sm',
                        msg.sender_type === 'operator' ? 'bg-blue-600 text-white rounded-br-none' : 
                        msg.sender_type === 'bot' ? 'bg-indigo-50 text-indigo-900 border border-indigo-100 rounded-bl-none italic' : 
                        'bg-white text-gray-800 border border-gray-100 rounded-bl-none']">
                            <div v-if="msg.image_url">
                                <img :src="`${API_URL}${msg.image_url}`" class="max-w-[200px] rounded-lg mb-1" />
                            </div>
                            <span v-if="msg.content">{{ msg.content }}</span>
                        </div>
                        <span :class="['text-[10px] text-gray-400 mt-1 flex items-center gap-1', msg.sender_type === 'operator' ? 'justify-end' : 'justify-start']">
                            <span v-if="msg.sender_type === 'bot'" class="flex items-center gap-1 text-indigo-500 font-bold">
                                🤖 自動応答
                            </span>
                            {{ new Date(msg.created_at).toLocaleTimeString() }}
                            <span v-if="msg.sender_type === 'operator' && msg.is_read" class="text-blue-600 font-bold text-[10px] ml-1">既読</span>
                        </span>
                     </div>
                </div>
            </div>
            
            <div class="p-4 bg-white border-t border-gray-200">
                <div class="max-w-4xl mx-auto flex gap-3 relative">
                    <input type="file" ref="fileInput" @change="handleFileUpload" accept="image/*" class="hidden" />
                    <button @click="triggerFileUpload" class="p-3 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors text-gray-600">
                        <ImageIcon size="20" />
                    </button>
                    <input v-model="newMessage" @keyup.enter="sendMessage"
                        class="flex-1 bg-gray-100 border-0 rounded-xl px-5 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all text-sm"
                        placeholder="返信を入力してください" />
                    <button @click="sendMessage" 
                            :disabled="!newMessage.trim()"
                            class="bg-blue-600 text-white px-5 py-3 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md flex items-center gap-2">
                        <span>送信 </span>
                        <Send size="18" />
                    </button>
                </div>
            </div>
        </template>
    </div>
  </div>
</template>
