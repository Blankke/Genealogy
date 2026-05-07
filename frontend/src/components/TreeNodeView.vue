<script setup lang="ts">
import { UserRound } from "lucide-vue-next";

import type { TreeNode } from "../types";

defineOptions({ name: "TreeNodeView" });

defineProps<{
  node: TreeNode;
}>();
</script>

<template>
  <li class="tree-node">
    <div class="tree-node__content">
      <UserRound class="icon-inline" />
      <span class="tree-node__name">{{ node.member.name }}</span>
      <span class="tree-node__meta">ID {{ node.member.id }}</span>
      <span class="tree-node__meta">第 {{ node.member.generation_index }} 代</span>
    </div>
    <ul v-if="node.children.length" class="tree-node__children">
      <TreeNodeView v-for="child in node.children" :key="child.member.id" :node="child" />
    </ul>
  </li>
</template>
