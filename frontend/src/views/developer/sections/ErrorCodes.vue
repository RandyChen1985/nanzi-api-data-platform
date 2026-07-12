<template>
  <div>
    <h2 class="text-xl font-semibold mb-6 text-gray-800">业务错误码字典</h2>
    <ClearableInput
      v-model="search"
      wrapper-class="mb-4"
      placeholder="搜索错误码或描述..."
      input-class="px-4 py-2"
    />
    
    <div class="overflow-x-auto border rounded-lg">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">错误码 (Code)</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">标识名 (Name)</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">说明 (Description)</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="item in filteredCodes" :key="item.code" class="hover:bg-gray-50 transition-colors">
            <td class="px-6 py-4 whitespace-nowrap font-mono text-sm font-semibold text-blue-600">{{ item.code }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ item.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ item.description }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import ClearableInput from '@/components/common/ClearableInput.vue'

interface ErrorCode {
  code: number
  name: string
  description: string
}

const codes = ref<ErrorCode[]>([])
const search = ref('')

const fetchCodes = async () => {
  try {
    const res = await axios.get('/api/portal/developer/error-codes')
    codes.value = res.data
  } catch (err) {
    console.error('Failed to fetch error codes', err)
  }
}

const filteredCodes = computed(() => {
  const s = search.value.toLowerCase()
  return codes.value.filter(c => 
    c.code.toString().includes(s) || 
    c.name.toLowerCase().includes(s) || 
    c.description.toLowerCase().includes(s)
  )
})

onMounted(fetchCodes)
</script>
