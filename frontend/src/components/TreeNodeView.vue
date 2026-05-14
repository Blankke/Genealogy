<script setup lang="ts">
import { ChevronDown, ChevronRight, Pencil, UserRound } from "lucide-vue-next";
import { computed, ref } from "vue";

import type { MemberRead, TreeNode } from "../types";

defineOptions({ name: "TreeNodeView" });

const props = defineProps<{
  node: TreeNode;
}>();

const emit = defineEmits<{
  editMember: [member: MemberRead];
}>();

// 默认只展开前两层，避免大树首次渲染时一次性挂载过多节点。
const expanded = ref(props.node.depth < 2);
const hasChildren = computed(() => props.node.children.length > 0);

function formatGender(gender: string) {
  return { male: "男", female: "女", unknown: "未知" }[gender] ?? gender;
}

function formatLifeSpan(birthDate: string | null, deathDate: string | null) {
  if (!birthDate && !deathDate) {
    return "生卒年未录入";
  }
  return `${birthDate || "未知"} - ${deathDate || "至今"}`;
}

function toggleExpanded() {
  if (!hasChildren.value) {
    return;
  }
  expanded.value = !expanded.value;
}

function editMember() {
  emit("editMember", props.node.member);
}
</script>

<template>
  <li class="tree-node" :class="{ 'tree-node-root': props.node.depth === 0 }">
    <article class="tree-node__card">
      <div class="tree-node__header">
        <div class="tree-node__identity">
          <button
            class="tree-node__toggle"
            :class="{ 'tree-node__toggle-placeholder': !hasChildren }"
            type="button"
            :disabled="!hasChildren"
            @click="toggleExpanded"
          >
            <ChevronDown v-if="hasChildren && expanded" class="icon-inline" />
            <ChevronRight v-else-if="hasChildren" class="icon-inline" />
          </button>
          <UserRound class="icon-inline" />
          <span class="tree-node__name">{{ props.node.member.name }}</span>
        </div>
        <div class="tree-node__badges">
          <span class="tree-node__badge tree-node__badge-primary">
            {{ props.node.depth === 0 ? "根节点" : `第 ${props.node.member.generation_index} 代` }}
          </span>
          <span class="tree-node__badge">{{ formatGender(props.node.member.gender) }}</span>
          <span class="tree-node__badge">子代 {{ props.node.children.length }} 人</span>
        </div>
      </div>

      <div class="tree-node__details">
        <span class="tree-node__meta">ID {{ props.node.member.id }}</span>
        <span class="tree-node__meta">层级深度 {{ props.node.depth }}</span>
        <span class="tree-node__meta">
          {{ formatLifeSpan(props.node.member.birth_date, props.node.member.death_date) }}
        </span>
      </div>

      <div class="tree-node__actions">
        <button class="button" type="button" @click="editMember">
          <Pencil class="icon-inline" />
          编辑
        </button>
      </div>
    </article>

    <ul v-if="hasChildren && expanded" class="tree-node__children">
      <TreeNodeView
        v-for="child in props.node.children"
        :key="child.member.id"
        :node="child"
        @edit-member="emit('editMember', $event)"
      />
    </ul>
  </li>
</template>
