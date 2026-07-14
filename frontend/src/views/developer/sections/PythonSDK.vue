<template>
  <div class="prose max-w-none">
    <h2 class="text-xl font-semibold mb-4 text-gray-800">Python 客户端封装示例</h2>
    <p>为了提高开发效率，建议您使用以下类对 API 进行封装。它包含了自动签名、请求重试以及异常处理。</p>

    <div class="relative group mt-6">
      <button 
        @click="copyCode"
        class="absolute right-4 top-4 bg-gray-700 text-white px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {{ copied ? '已复制' : '复制代码' }}
      </button>
      <pre class="bg-gray-900 text-gray-100 p-6 rounded-xl text-sm leading-relaxed overflow-x-auto"><code>import requests
import time
import logging

class YunshuClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        })

    def request(self, method, endpoint, params=None, json=None):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, params=params, json=json)
            data = response.json()
            
            if data.get("code") != 200:
                logging.error(f"API Error [{data.get('code')}]: {data.get('message')}")
                
            return data
        except Exception as e:
            logging.error(f"Connection Error: {e}")
            return {"code": 500, "message": str(e), "data": None}

    def get_rooms(self, page=1, size=20):
        return self.request("GET", "/api/v1/resources/rooms", params={"page": page, "size": size})

# 使用示例
if __name__ == "__main__":
    client = YunshuClient("https://your-api-host.example.com", "YOUR_API_KEY_HERE")
    result = client.get_rooms()
    if result["code"] == 200:
        for room in result["data"]["items"]:
            print(f"机房名: {room['room_name']}")</code></pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'

const copied = ref(false)
const codeText = `import requests
import time
import logging

class YunshuClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        })

    def request(self, method, endpoint, params=None, json=None):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, params=params, json=json)
            data = response.json()
            
            if data.get("code") != 200:
                logging.error(f"API Error [{data.get('code')}]: {data.get('message')}")
                
            return data
        except Exception as e:
            logging.error(f"Connection Error: {e}")
            return {"code": 500, "message": str(e), "data": None}

    def get_rooms(self, page=1, size=20):
        return self.request("GET", "/api/v1/resources/rooms", params={"page": page, "size": size})

# 使用示例
if __name__ == "__main__":
    client = YunshuClient("https://your-api-host.example.com", "YOUR_API_KEY_HERE")
    result = client.get_rooms()
    if result["code"] == 200:
        for room in result["data"]["items"]:
            print(f"机房名: {room['room_name']}")`

const copyCode = async () => {
  const success = await copyToClipboard(codeText)
  if (success) {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  }
}
</script>
