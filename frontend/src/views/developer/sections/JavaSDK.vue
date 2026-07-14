<template>
  <div class="prose max-w-none">
    <h2 class="text-xl font-semibold mb-4 text-gray-800">Java 客户端封装示例 (OkHttp)</h2>
    <p>以下是使用 OkHttp 库封装的 Java 客户端示例，包含了 API Key 认证和响应处理逻辑。</p>

    <div class="relative group mt-6">
      <button 
        @click="copyCode"
        class="absolute right-4 top-4 bg-gray-700 text-white px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {{ copied ? '已复制' : '复制代码' }}
      </button>
      <pre class="bg-gray-900 text-gray-100 p-6 rounded-xl text-sm leading-relaxed overflow-x-auto"><code>import okhttp3.*;
import java.io.IOException;

public class YunshuClient {
    private final String baseUrl;
    private final String apiKey;
    private final OkHttpClient client;

    public YunshuClient(String baseUrl, String apiKey) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.apiKey = apiKey;
        this.client = new OkHttpClient();
    }

    private String request(String method, String endpoint) throws IOException {
        Request request = new Request.Builder()
                .url(this.baseUrl + endpoint)
                .addHeader("X-API-Key", this.apiKey)
                .addHeader("Content-Type", "application/json")
                .method(method, null)
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                System.err.println("API Error: " + response.code());
            }
            return response.body().string();
        }
    }

    public String getRooms(int page, int size) throws IOException {
        return request("GET", "/api/v1/resources/rooms?page=" + page + "&size=" + size);
    }

    public static void main(String[] args) {
        YunshuClient client = new YunshuClient("https://your-api-host.example.com", "YOUR_API_KEY_HERE");
        try {
            String rooms = client.getRooms(1, 20);
            System.out.println(rooms);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}</code></pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'

const copied = ref(false)
const codeText = `import okhttp3.*;
import java.io.IOException;

public class YunshuClient {
    private final String baseUrl;
    private final String apiKey;
    private final OkHttpClient client;

    public YunshuClient(String baseUrl, String apiKey) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.apiKey = apiKey;
        this.client = new OkHttpClient();
    }

    private String request(String method, String endpoint) throws IOException {
        Request request = new Request.Builder()
                .url(this.baseUrl + endpoint)
                .addHeader("X-API-Key", this.apiKey)
                .addHeader("Content-Type", "application/json")
                .method(method, null)
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                System.err.println("API Error: " + response.code());
            }
            return response.body().string();
        }
    }

    public String getRooms(int page, int size) throws IOException {
        return request("GET", "/api/v1/resources/rooms?page=" + page + "&size=" + size);
    }

    public static void main(String[] args) {
        YunshuClient client = new YunshuClient("https://your-api-host.example.com", "YOUR_API_KEY_HERE");
        try {
            String rooms = client.getRooms(1, 20);
            System.out.println(rooms);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}`

const copyCode = async () => {
  const success = await copyToClipboard(codeText)
  if (success) {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  }
}
</script>
