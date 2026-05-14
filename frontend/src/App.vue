<script setup lang="ts">
import {
  GitBranch,
  HeartHandshake,
  LogOut,
  Network,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ScrollText,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
  Database,
} from "lucide-vue-next";
import { computed, reactive, ref } from "vue";

import { ApiError, createApiClient } from "./api";
import TreeNodeView from "./components/TreeNodeView.vue";
import type {
  AdminDashboardRead,
  AncestorRead,
  CommonAncestorRead,
  DashboardRead,
  FamilyRead,
  GenealogyRead,
  MemberRead,
  RelationshipPathRead,
  SqlQueryDefinitionRead,
  SqlQueryResultRead,
  TreeNode,
  UserRead,
} from "./types";

type TabKey = "admin" | "dashboard" | "members" | "tree" | "ancestors" | "relation" | "sql";
type AuthMode = "login" | "register";
type AncestorQueryMode = "single" | "common";

const apiBaseUrl = ref(localStorage.getItem("apiBaseUrl") || "http://localhost:8000");
const token = ref(localStorage.getItem("token") || "");
const activeTab = ref<TabKey>("dashboard");
const authMode = ref<AuthMode>("login");
const loading = ref(false);
const message = ref("");

const user = ref<UserRead | null>(null);
const genealogies = ref<GenealogyRead[]>([]);
const selectedGenealogyId = ref<number | null>(null);
const adminDashboard = ref<AdminDashboardRead | null>(null);
const dashboard = ref<DashboardRead | null>(null);
const members = ref<MemberRead[]>([]);
const memberPageSizes = [50, 100, 200] as const;
const memberLimit = ref<(typeof memberPageSizes)[number]>(50);
const memberOffset = ref(0);
const memberTotal = ref(0);
const memberPageInput = ref("1");
const family = ref<FamilyRead | null>(null);
const ancestors = ref<AncestorRead[]>([]);
const commonAncestors = ref<CommonAncestorRead[]>([]);
const ancestorResultMode = ref<AncestorQueryMode | null>(null);
const selectedAncestorMember = ref<MemberRead | null>(null);
const tree = ref<TreeNode[]>([]);
const treePage = ref(1);
const treePageInput = ref("1");
const treePageSize = ref(1500);
const treePageNodes = ref(0);
const treeTotalNodes = ref(0);
const treeTotalPages = ref(1);
const relationshipPath = ref<RelationshipPathRead | null>(null);
const sqlQueryDefinitions = ref<SqlQueryDefinitionRead[]>([]);
const selectedSqlQueryKey = ref("");
const sqlQueryMemberId = ref("");
const sqlQueryResult = ref<SqlQueryResultRead | null>(null);
const selectedMemberEditor = ref<MemberRead | null>(null);

const authForm = reactive({
  username: "",
  email: "",
  password: "",
});

const genealogyForm = reactive({
  name: "",
  surname: "",
  revision_time: "",
});

const inviteForm = reactive({
  email: "",
  role: "editor",
});

const memberSearch = ref("");
const memberForm = reactive({
  name: "",
  gender: "male",
  birth_date: "",
  death_date: "",
  generation_index: 1,
  biography: "",
});

const memberEditForm = reactive({
  name: "",
  gender: "male",
  birth_date: "",
  death_date: "",
  generation_index: 1,
  biography: "",
});

const parentChildForm = reactive({
  parent_id: "",
  child_id: "",
  parent_role: "father",
});

const marriageForm = reactive({
  spouse_a_id: "",
  spouse_b_id: "",
  start_date: "",
  end_date: "",
  status: "active",
});

const memberRelationForm = reactive({
  father_id: "",
  mother_id: "",
  spouse_id: "",
  spouse_start_date: "",
});

const queryForm = reactive({
  family_member_id: "",
  tree_root_member_id: "",
  tree_max_depth: 3,
  ancestor_member_id: "",
  common_ancestor_first_member_id: "",
  common_ancestor_second_member_id: "",
  source_member_id: "",
  target_member_id: "",
});

const tabs = [
  { key: "dashboard", label: "概览", icon: ShieldCheck },
  { key: "members", label: "成员", icon: Users },
  { key: "tree", label: "树形", icon: GitBranch },
  { key: "ancestors", label: "祖先", icon: Network },
  { key: "relation", label: "亲缘", icon: HeartHandshake },
  { key: "sql", label: "SQL 查询", icon: ScrollText },
] as const;

const adminTab = { key: "admin", label: "系统总览", icon: Database } as const;

const api = createApiClient({
  getBaseUrl: () => apiBaseUrl.value,
  getToken: () => token.value,
});

const selectedGenealogy = computed(() =>
  genealogies.value.find((genealogy) => genealogy.id === selectedGenealogyId.value),
);

const selectedGenealogyReady = computed(() => selectedGenealogyId.value !== null);
const visibleTabs = computed(() => (user.value?.is_admin ? [adminTab, ...tabs] : tabs));
const memberPage = computed(() => Math.floor(memberOffset.value / memberLimit.value) + 1);
const memberTotalPages = computed(() =>
  Math.max(1, Math.ceil(memberTotal.value / memberLimit.value)),
);
const memberRangeStart = computed(() => (memberTotal.value === 0 ? 0 : memberOffset.value + 1));
const memberRangeEnd = computed(() =>
  Math.min(memberOffset.value + members.value.length, memberTotal.value),
);
const canLoadPreviousMembers = computed(() => memberOffset.value > 0);
const canLoadNextMembers = computed(
  () => memberOffset.value + members.value.length < memberTotal.value,
);
const canLoadPreviousTreePage = computed(() => treePage.value > 1);
const canLoadNextTreePage = computed(() => treePage.value < treeTotalPages.value);
const selectedSqlDefinition = computed(
  () => sqlQueryDefinitions.value.find((query) => query.key === selectedSqlQueryKey.value) ?? null,
);
const selectedSqlNeedsMemberId = computed(
  () => selectedSqlDefinition.value?.required_params.includes("member_id") ?? false,
);

function clampPageNumber(value: string | number, totalPages: number) {
  const parsed =
    typeof value === "number" ? value : Number.parseInt(String(value).trim(), 10);
  if (Number.isNaN(parsed)) {
    return 1;
  }
  return Math.min(Math.max(parsed, 1), Math.max(totalPages, 1));
}

function formatGender(gender: string) {
  return { male: "男", female: "女", unknown: "未知" }[gender] ?? gender;
}

function formatAncestorRole(role: string) {
  return role === "father" ? "父系" : "母系";
}

function formatAncestorRoles(roles: string[]) {
  return roles.map(formatAncestorRole).join(" / ");
}

function normalizeDate(value: string) {
  return value || null;
}

function openAncestorMemberDetail(member: MemberRead) {
  selectedAncestorMember.value = member;
}

function clearAncestorResults() {
  ancestors.value = [];
  commonAncestors.value = [];
  ancestorResultMode.value = null;
  selectedAncestorMember.value = null;
}

function clearSqlQueryState() {
  sqlQueryDefinitions.value = [];
  selectedSqlQueryKey.value = "";
  sqlQueryMemberId.value = "";
  sqlQueryResult.value = null;
}

function openMemberEditor(member: MemberRead) {
  selectedMemberEditor.value = member;
  memberEditForm.name = member.name;
  memberEditForm.gender = member.gender;
  memberEditForm.birth_date = member.birth_date || "";
  memberEditForm.death_date = member.death_date || "";
  memberEditForm.generation_index = member.generation_index;
  memberEditForm.biography = member.biography;
  memberRelationForm.father_id = "";
  memberRelationForm.mother_id = "";
  memberRelationForm.spouse_id = "";
  memberRelationForm.spouse_start_date = "";
}

function clearMemberEditor() {
  selectedMemberEditor.value = null;
  memberRelationForm.father_id = "";
  memberRelationForm.mother_id = "";
  memberRelationForm.spouse_id = "";
  memberRelationForm.spouse_start_date = "";
}

function formatSqlCell(value: unknown) {
  if (value === null || value === undefined) {
    return "NULL";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function validateAuthForm() {
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (authMode.value === "register") {
    const username = authForm.username.trim();
    if (username.length < 2 || username.length > 64) {
      return "注册失败：用户名必填，长度需要在 2 到 64 个字符之间。";
    }
  }
  if (!emailPattern.test(authForm.email.trim())) {
    return "注册失败：邮箱格式不正确，例如 test01@example.com。";
  }
  if (authForm.password.length < 6 || authForm.password.length > 128) {
    return "注册失败：密码长度需要在 6 到 128 个字符之间。";
  }
  return "";
}

async function runTask(task: () => Promise<void>, successMessage?: string) {
  loading.value = true;
  message.value = "";
  try {
    await task();
    if (successMessage) {
      message.value = successMessage;
    }
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : "操作失败";
  } finally {
    loading.value = false;
  }
}

async function boot() {
  if (!token.value) {
    return;
  }
  await runTask(async () => {
    user.value = await api.me();
    await refreshGenealogies();
  });
}

async function submitAuth() {
  const validationMessage = validateAuthForm();
  if (validationMessage) {
    message.value = validationMessage;
    return;
  }
  await runTask(async () => {
    const response =
      authMode.value === "login"
        ? await api.login(authForm.email, authForm.password)
        : await api.register(authForm.username, authForm.email, authForm.password);
    token.value = response.access_token;
    localStorage.setItem("token", token.value);
    localStorage.setItem("apiBaseUrl", apiBaseUrl.value);
    await boot();
  }, "已登录");
}

function logout() {
  token.value = "";
  localStorage.removeItem("token");
  user.value = null;
  genealogies.value = [];
  selectedGenealogyId.value = null;
  memberPageInput.value = "1";
  tree.value = [];
  treePage.value = 1;
  treePageInput.value = "1";
  treePageNodes.value = 0;
  treeTotalNodes.value = 0;
  treeTotalPages.value = 1;
  family.value = null;
  parentChildForm.parent_id = "";
  parentChildForm.child_id = "";
  parentChildForm.parent_role = "father";
  marriageForm.spouse_a_id = "";
  marriageForm.spouse_b_id = "";
  marriageForm.start_date = "";
  marriageForm.end_date = "";
  marriageForm.status = "active";
  clearAncestorResults();
  clearSqlQueryState();
  clearMemberEditor();
}

async function refreshGenealogies() {
  genealogies.value = await api.listGenealogies();
  if (!selectedGenealogyId.value && genealogies.value.length) {
    selectedGenealogyId.value = genealogies.value[0].id;
  }
  await refreshCurrentView();
}

async function refreshCurrentView() {
  if (activeTab.value === "admin") {
    adminDashboard.value = await api.adminDashboard();
    return;
  }
  if (!selectedGenealogyId.value) {
    return;
  }
  if (activeTab.value === "dashboard") {
    dashboard.value = await api.dashboard(selectedGenealogyId.value);
  }
  if (activeTab.value === "members") {
    await loadMembers();
  }
  if (activeTab.value === "sql") {
    await loadSqlQueries();
  }
}

async function createGenealogy() {
  await runTask(async () => {
    const created = await api.createGenealogy({
      name: genealogyForm.name,
      surname: genealogyForm.surname,
      revision_time: normalizeDate(genealogyForm.revision_time),
    });
    selectedGenealogyId.value = created.id;
    genealogyForm.name = "";
    genealogyForm.surname = "";
    genealogyForm.revision_time = "";
    await refreshGenealogies();
  }, "族谱已创建");
}

async function inviteCollaborator() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    await api.inviteCollaborator(selectedGenealogyId.value!, inviteForm.email, inviteForm.role);
    inviteForm.email = "";
  }, "协作者已邀请");
}

// 成员数量可能很大，这里统一通过分页接口加载，避免一次性渲染过多数据。
async function loadMembers(resetOffset = false) {
  if (!selectedGenealogyId.value) return;
  if (resetOffset) {
    memberOffset.value = 0;
  }
  const response = await api.listMembers(selectedGenealogyId.value, {
    search: memberSearch.value,
    limit: memberLimit.value,
    offset: memberOffset.value,
  });
  members.value = response.items;
  memberTotal.value = response.total;
  memberPageInput.value = String(memberPage.value);
}

async function searchMembers() {
  await runTask(async () => {
    await loadMembers(true);
  });
}

async function createMember() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    await api.createMember(selectedGenealogyId.value!, {
      ...memberForm,
      birth_date: normalizeDate(memberForm.birth_date),
      death_date: normalizeDate(memberForm.death_date),
    });
    memberForm.name = "";
    memberForm.biography = "";
    await loadMembers();
  }, "成员已创建");
}

async function saveMemberEdits() {
  if (!selectedMemberEditor.value) return;
  await runTask(async () => {
    const updated = await api.updateMember(selectedMemberEditor.value!.id, {
      ...memberEditForm,
      birth_date: normalizeDate(memberEditForm.birth_date),
      death_date: normalizeDate(memberEditForm.death_date),
    });
    members.value = members.value.map((member) =>
      member.id === updated.id ? updated : member,
    );
    openMemberEditor(updated);
  }, "成员信息已更新");
}

async function deleteMemberFromList(member: MemberRead) {
  if (!window.confirm(`确认删除成员“${member.name}”（ID ${member.id}）吗？`)) {
    return;
  }

  await runTask(async () => {
    await api.deleteMember(member.id);
    if (selectedMemberEditor.value?.id === member.id) {
      clearMemberEditor();
    }

    const nextTotal = Math.max(memberTotal.value - 1, 0);
    if (memberOffset.value >= nextTotal && memberOffset.value > 0) {
      memberOffset.value = Math.max(0, memberOffset.value - memberLimit.value);
    }
    await loadMembers();
  }, "成员已删除");
}

function openMemberEditorFromTree(member: MemberRead) {
  activeTab.value = "members";
  openMemberEditor(member);
}

async function changeMemberPageSize() {
  await runTask(async () => {
    await loadMembers(true);
  });
}

async function loadMembersPage(page: number) {
  memberOffset.value = (clampPageNumber(page, memberTotalPages.value) - 1) * memberLimit.value;
  await loadMembers();
}

async function loadPreviousMembersPage() {
  if (!canLoadPreviousMembers.value) return;
  await runTask(async () => {
    await loadMembersPage(memberPage.value - 1);
  });
}

async function loadNextMembersPage() {
  if (!canLoadNextMembers.value) return;
  await runTask(async () => {
    await loadMembersPage(memberPage.value + 1);
  });
}

async function jumpToMemberPage() {
  await runTask(async () => {
    const targetPage = clampPageNumber(memberPageInput.value, memberTotalPages.value);
    memberPageInput.value = String(targetPage);
    await loadMembersPage(targetPage);
  });
}

async function loadLastMembersPage() {
  if (memberTotalPages.value <= 1 || memberPage.value === memberTotalPages.value) return;
  await runTask(async () => {
    await loadMembersPage(memberTotalPages.value);
  });
}

async function createParentChild() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    await api.createParentChild(selectedGenealogyId.value!, {
      parent_id: Number(parentChildForm.parent_id),
      child_id: Number(parentChildForm.child_id),
      parent_role: parentChildForm.parent_role,
    });
    parentChildForm.parent_id = "";
    parentChildForm.child_id = "";
  }, "亲子关系已创建");
}

async function createMarriage() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    await api.createMarriage(selectedGenealogyId.value!, {
      spouse_a_id: Number(marriageForm.spouse_a_id),
      spouse_b_id: Number(marriageForm.spouse_b_id),
      start_date: normalizeDate(marriageForm.start_date),
      end_date: normalizeDate(marriageForm.end_date),
      status: marriageForm.status,
    });
    marriageForm.spouse_a_id = "";
    marriageForm.spouse_b_id = "";
  }, "婚姻关系已创建");
}

async function addParentForSelectedMember(parentRole: "father" | "mother") {
  if (!selectedGenealogyId.value || !selectedMemberEditor.value) return;
  const parentId =
    parentRole === "father" ? memberRelationForm.father_id : memberRelationForm.mother_id;
  await runTask(async () => {
    await api.createParentChild(selectedGenealogyId.value!, {
      parent_id: Number(parentId),
      child_id: selectedMemberEditor.value!.id,
      parent_role: parentRole,
    });
    if (parentRole === "father") {
      memberRelationForm.father_id = "";
    } else {
      memberRelationForm.mother_id = "";
    }
  }, parentRole === "father" ? "已为当前成员添加父亲关系" : "已为当前成员添加母亲关系");
}

async function addSpouseForSelectedMember() {
  if (!selectedGenealogyId.value || !selectedMemberEditor.value) return;
  await runTask(async () => {
    await api.createMarriage(selectedGenealogyId.value!, {
      spouse_a_id: selectedMemberEditor.value!.id,
      spouse_b_id: Number(memberRelationForm.spouse_id),
      start_date: normalizeDate(memberRelationForm.spouse_start_date),
      end_date: null,
      status: "active",
    });
    memberRelationForm.spouse_id = "";
    memberRelationForm.spouse_start_date = "";
  }, "已为当前成员添加配偶关系");
}

async function loadFamily() {
  await runTask(async () => {
    family.value = await api.family(Number(queryForm.family_member_id));
  });
}

async function loadTreePage(page = 1) {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    tree.value = [];
    const targetPage = clampPageNumber(page, treeTotalPages.value);
    const response = await api.tree(
      selectedGenealogyId.value!,
      queryForm.tree_root_member_id,
      queryForm.tree_max_depth,
      targetPage,
    );
    tree.value = response.items;
    treePage.value = response.page;
    treePageInput.value = String(response.page);
    treePageSize.value = response.page_size;
    treePageNodes.value = response.page_nodes;
    treeTotalNodes.value = response.total_nodes;
    treeTotalPages.value = response.total_pages;
  });
}

async function loadTree() {
  await loadTreePage(1);
}

async function loadPreviousTreePage() {
  if (!canLoadPreviousTreePage.value) return;
  await loadTreePage(treePage.value - 1);
}

async function loadNextTreePage() {
  if (!canLoadNextTreePage.value) return;
  await loadTreePage(treePage.value + 1);
}

async function jumpToTreePage() {
  const targetPage = clampPageNumber(treePageInput.value, treeTotalPages.value);
  treePageInput.value = String(targetPage);
  await loadTreePage(targetPage);
}

async function loadLastTreePage() {
  if (treeTotalPages.value <= 1 || treePage.value === treeTotalPages.value) return;
  await loadTreePage(treeTotalPages.value);
}

async function loadAncestors() {
  await runTask(async () => {
    ancestors.value = await api.ancestors(Number(queryForm.ancestor_member_id));
    commonAncestors.value = [];
    ancestorResultMode.value = "single";
    selectedAncestorMember.value = ancestors.value[0]?.member ?? null;
  });
}

async function loadCommonAncestors() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    commonAncestors.value = await api.commonAncestors(
      selectedGenealogyId.value!,
      queryForm.common_ancestor_first_member_id,
      queryForm.common_ancestor_second_member_id,
    );
    ancestors.value = [];
    ancestorResultMode.value = "common";
    selectedAncestorMember.value = commonAncestors.value[0]?.member ?? null;
  });
}

async function loadSqlQueries() {
  if (!selectedGenealogyId.value) return;
  sqlQueryDefinitions.value = await api.listSqlQueries(selectedGenealogyId.value);
  if (!selectedSqlQueryKey.value && sqlQueryDefinitions.value.length > 0) {
    selectedSqlQueryKey.value = sqlQueryDefinitions.value[0].key;
  }
}

function handleSqlQueryChange() {
  sqlQueryResult.value = null;
}

async function runSelectedSqlQuery() {
  if (!selectedGenealogyId.value || !selectedSqlDefinition.value) return;
  await runTask(async () => {
    const payload: { query_key: string; member_id?: number } = {
      query_key: selectedSqlDefinition.value!.key,
    };
    if (selectedSqlNeedsMemberId.value) {
      payload.member_id = Number(sqlQueryMemberId.value);
    }
    sqlQueryResult.value = await api.runSqlQuery(selectedGenealogyId.value!, payload);
  });
}

async function loadRelationshipPath() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    relationshipPath.value = await api.relationshipPath(
      selectedGenealogyId.value!,
      queryForm.source_member_id,
      queryForm.target_member_id,
    );
  });
}

async function handleGenealogyChange() {
  memberOffset.value = 0;
  memberPageInput.value = "1";
  tree.value = [];
  treePage.value = 1;
  treePageInput.value = "1";
  treePageNodes.value = 0;
  treeTotalNodes.value = 0;
  treeTotalPages.value = 1;
  family.value = null;
  parentChildForm.parent_id = "";
  parentChildForm.child_id = "";
  parentChildForm.parent_role = "father";
  marriageForm.spouse_a_id = "";
  marriageForm.spouse_b_id = "";
  marriageForm.start_date = "";
  marriageForm.end_date = "";
  marriageForm.status = "active";
  clearAncestorResults();
  clearSqlQueryState();
  clearMemberEditor();
  await refreshCurrentView();
}

boot();
</script>

<template>
  <main class="app">
    <section v-if="!token" class="auth-layout">
      <form class="auth-card" @submit.prevent="submitAuth">
        <div class="brand">
          <GitBranch class="icon-standalone" />
          <h1>族谱管理系统</h1>
        </div>
        <label class="field">
          <span>API 地址</span>
          <input v-model="apiBaseUrl" type="url" required />
        </label>
        <label v-if="authMode === 'register'" class="field">
          <span>用户名</span>
          <input
            v-model.trim="authForm.username"
            type="text"
            autocomplete="username"
            minlength="2"
            maxlength="64"
            placeholder="例如 test01"
            required
          />
          <small class="field-help">注册必填，2 到 64 个字符。</small>
        </label>
        <label class="field">
          <span>邮箱</span>
          <input
            v-model.trim="authForm.email"
            type="email"
            autocomplete="email"
            placeholder="例如 test01@example.com"
            required
          />
          <small class="field-help">必须是合法邮箱格式。</small>
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="authForm.password"
            type="password"
            autocomplete="current-password"
            minlength="6"
            maxlength="128"
            placeholder="至少 6 位"
            required
          />
          <small class="field-help">长度需要在 6 到 128 个字符之间。</small>
        </label>
        <button class="button button-primary" type="submit" :disabled="loading">
          <ShieldCheck class="icon-inline" />
          {{ authMode === "login" ? "登录" : "注册" }}
        </button>
        <button
          class="button button-ghost"
          type="button"
          @click="authMode = authMode === 'login' ? 'register' : 'login'"
        >
          {{ authMode === "login" ? "切换注册" : "切换登录" }}
        </button>
        <p v-if="message" class="message">{{ message }}</p>
      </form>
    </section>

    <section v-else class="workspace">
      <aside class="sidebar">
        <div class="brand brand-compact">
          <GitBranch class="icon-standalone" />
          <h1>族谱</h1>
        </div>
        <div class="user-box">
          <span>{{ user?.username }}</span>
          <small>{{ user?.email }}</small>
        </div>
        <label class="field">
          <span>当前族谱</span>
          <select v-model.number="selectedGenealogyId" @change="handleGenealogyChange">
            <option v-for="genealogy in genealogies" :key="genealogy.id" :value="genealogy.id">
              {{ genealogy.name }}
            </option>
          </select>
        </label>
        <nav class="tabs">
          <button
            v-for="tab in visibleTabs"
            :key="tab.key"
            class="tab-button"
            :class="{ 'tab-button-active': activeTab === tab.key }"
            type="button"
            @click="
              activeTab = tab.key;
              refreshCurrentView();
            "
          >
            <component :is="tab.icon" class="icon-inline" />
            {{ tab.label }}
          </button>
        </nav>
        <button class="button button-ghost" type="button" @click="logout">
          <LogOut class="icon-inline" />
          退出
        </button>
      </aside>

      <section class="content">
        <header class="page-header">
          <div>
            <h2>{{ selectedGenealogy?.name || "尚未选择族谱" }}</h2>
            <p>{{ selectedGenealogy?.surname || "创建一个族谱开始录入成员" }}</p>
          </div>
          <button class="button" type="button" :disabled="loading" @click="refreshCurrentView">
            <RefreshCw class="icon-inline" />
            刷新
          </button>
        </header>

        <p v-if="message" class="message">{{ message }}</p>

        <section v-if="activeTab === 'admin'" class="view-stack">
          <div class="stats-grid">
            <article class="stat-card">
              <span>系统用户</span>
              <strong>{{ adminDashboard?.total_users ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>族谱总数</span>
              <strong>{{ adminDashboard?.total_genealogies ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>系统成员</span>
              <strong>{{ adminDashboard?.total_members ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>亲子关系</span>
              <strong>{{ adminDashboard?.total_parent_child_relations ?? 0 }}</strong>
            </article>
          </div>
          <div class="stats-grid">
            <article class="stat-card">
              <span>男性成员</span>
              <strong>{{ adminDashboard?.male_count ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>女性成员</span>
              <strong>{{ adminDashboard?.female_count ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>未知性别</span>
              <strong>{{ adminDashboard?.unknown_count ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>婚姻关系</span>
              <strong>{{ adminDashboard?.total_marriages ?? 0 }}</strong>
            </article>
          </div>
          <div class="panel table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>谱名</th>
                  <th>姓氏</th>
                  <th>创建用户</th>
                  <th>修谱时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="genealogy in genealogies" :key="genealogy.id">
                  <td>{{ genealogy.id }}</td>
                  <td>{{ genealogy.name }}</td>
                  <td>{{ genealogy.surname }}</td>
                  <td>{{ genealogy.owner_user_id }}</td>
                  <td>{{ genealogy.revision_time || "-" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <form class="form-grid" @submit.prevent="createGenealogy">
            <h3>新建族谱</h3>
            <input v-model="genealogyForm.name" placeholder="谱名" required />
            <input v-model="genealogyForm.surname" placeholder="姓氏" required />
            <input v-model="genealogyForm.revision_time" type="date" />
            <button class="button button-primary" type="submit">
              <Plus class="icon-inline" />
              创建
            </button>
          </form>
        </section>

        <section v-if="activeTab === 'dashboard'" class="view-stack">
          <div class="stats-grid">
            <article class="stat-card">
              <span>总人数</span>
              <strong>{{ dashboard?.total_members ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>男性</span>
              <strong>{{ dashboard?.male_count ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>女性</span>
              <strong>{{ dashboard?.female_count ?? 0 }}</strong>
            </article>
            <article class="stat-card">
              <span>未知</span>
              <strong>{{ dashboard?.unknown_count ?? 0 }}</strong>
            </article>
          </div>
          <form class="panel form-grid" @submit.prevent="inviteCollaborator">
            <h3>邀请协作者</h3>
            <input v-model="inviteForm.email" type="email" placeholder="邮箱" required />
            <select v-model="inviteForm.role">
              <option value="editor">编辑者</option>
              <option value="viewer">查看者</option>
            </select>
            <button class="button button-primary" type="submit" :disabled="!selectedGenealogyReady">
              <UserPlus class="icon-inline" />
              邀请
            </button>
          </form>
        </section>
        <section v-if="activeTab === 'members'" class="view-stack">
          <form class="panel search-row" @submit.prevent="searchMembers">
            <input v-model="memberSearch" placeholder="按姓名模糊查询成员" />
            <select v-model.number="memberLimit" @change="changeMemberPageSize">
              <option v-for="pageSize in memberPageSizes" :key="pageSize" :value="pageSize">
                每页 {{ pageSize }} 条
              </option>
            </select>
            <button class="button button-primary" type="submit">
              <Search class="icon-inline" />
              查询
            </button>
          </form>

          <div class="panel table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th class="member-action-column">操作</th>
                  <th>姓名</th>
                  <th>性别</th>
                  <th>出生日期</th>
                  <th>死亡日期</th>
                  <th>代际</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in members" :key="member.id">
                  <td>{{ member.id }}</td>
                  <td class="member-action-column">
                    <div class="member-action-group">
                      <button class="button" type="button" @click="openMemberEditor(member)">
                        <Pencil class="icon-inline" />
                        编辑
                      </button>
                      <button class="button button-danger" type="button" @click="deleteMemberFromList(member)">
                        <Trash2 class="icon-inline" />
                        删除
                      </button>
                    </div>
                  </td>
                  <td>{{ member.name }}</td>
                  <td>{{ formatGender(member.gender) }}</td>
                  <td>{{ member.birth_date || "-" }}</td>
                  <td>{{ member.death_date || "-" }}</td>
                  <td>{{ member.generation_index }}</td>
                </tr>
              </tbody>
            </table>
            <div class="pagination-bar">
              <p class="pagination-summary">
                共 {{ memberTotal }} 人，当前显示 {{ memberRangeStart }} - {{ memberRangeEnd }}，第
                {{ memberPage }} / {{ memberTotalPages }} 页
              </p>
              <div class="pagination-actions">
                <button
                  class="button"
                  type="button"
                  :disabled="loading || !canLoadPreviousMembers"
                  @click="loadPreviousMembersPage"
                >
                  上一页
                </button>
                <label class="pagination-jump">
                  <span>跳至</span>
                  <input
                    v-model="memberPageInput"
                    type="number"
                    min="1"
                    :max="memberTotalPages"
                    @keyup.enter="jumpToMemberPage"
                  />
                </label>
                <button class="button" type="button" :disabled="loading" @click="jumpToMemberPage">
                  跳转
                </button>
                <button
                  class="button"
                  type="button"
                  :disabled="loading || !canLoadNextMembers"
                  @click="loadNextMembersPage"
                >
                  下一页
                </button>
                <button
                  class="button"
                  type="button"
                  :disabled="loading || memberPage === memberTotalPages"
                  @click="loadLastMembersPage"
                >
                  最后一页
                </button>
              </div>
            </div>
          </div>

          <div v-if="selectedMemberEditor" class="panel view-stack">
            <div class="member-editor-header">
              <div>
                <h3>编辑成员：{{ selectedMemberEditor.name }}</h3>
                <p class="tree-hint">当前成员 ID：{{ selectedMemberEditor.id }}</p>
              </div>
              <div class="member-action-group">
                <button
                  class="button button-danger"
                  type="button"
                  @click="deleteMemberFromList(selectedMemberEditor)"
                >
                  <Trash2 class="icon-inline" />
                  删除成员
                </button>
                <button class="button" type="button" @click="clearMemberEditor">结束编辑</button>
              </div>
            </div>

            <form class="form-grid" @submit.prevent="saveMemberEdits">
              <input v-model="memberEditForm.name" placeholder="姓名" required />
              <select v-model="memberEditForm.gender">
                <option value="male">男</option>
                <option value="female">女</option>
                <option value="unknown">未知</option>
              </select>
              <input v-model="memberEditForm.birth_date" type="date" />
              <input v-model="memberEditForm.death_date" type="date" />
              <input v-model.number="memberEditForm.generation_index" type="number" min="1" />
              <textarea v-model="memberEditForm.biography" placeholder="生平简介"></textarea>
              <button class="button button-primary" type="submit">
                <Pencil class="icon-inline" />
                保存修改
              </button>
            </form>

            <div class="member-quick-actions">
              <form class="search-row" @submit.prevent="addParentForSelectedMember('father')">
                <input v-model="memberRelationForm.father_id" type="number" placeholder="父亲成员 ID" required />
                <button class="button" type="submit">添加父亲</button>
              </form>
              <form class="search-row" @submit.prevent="addParentForSelectedMember('mother')">
                <input v-model="memberRelationForm.mother_id" type="number" placeholder="母亲成员 ID" required />
                <button class="button" type="submit">添加母亲</button>
              </form>
              <form class="search-row" @submit.prevent="addSpouseForSelectedMember">
                <input v-model="memberRelationForm.spouse_id" type="number" placeholder="配偶成员 ID" required />
                <input v-model="memberRelationForm.spouse_start_date" type="date" />
                <button class="button" type="submit">添加配偶</button>
              </form>
            </div>
          </div>

          <form class="panel form-grid" @submit.prevent="createMember">
            <h3>新增成员</h3>
            <input v-model="memberForm.name" placeholder="姓名" required />
            <select v-model="memberForm.gender">
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="unknown">未知</option>
            </select>
            <input v-model="memberForm.birth_date" type="date" />
            <input v-model="memberForm.death_date" type="date" />
            <input v-model.number="memberForm.generation_index" type="number" min="1" />
            <textarea v-model="memberForm.biography" placeholder="生平简介"></textarea>
            <button class="button button-primary" type="submit">
              <Plus class="icon-inline" />
              保存成员
            </button>
          </form>

          <form class="panel form-grid" @submit.prevent="createParentChild">
            <h3>创建亲子关系</h3>
            <input v-model="parentChildForm.parent_id" type="number" placeholder="父亲或母亲 ID" required />
            <input v-model="parentChildForm.child_id" type="number" placeholder="子女 ID" required />
            <select v-model="parentChildForm.parent_role">
              <option value="father">父亲</option>
              <option value="mother">母亲</option>
            </select>
            <button class="button button-primary" type="submit">
              <Plus class="icon-inline" />
              建立关系
            </button>
          </form>

          <form class="panel form-grid" @submit.prevent="createMarriage">
            <h3>创建婚姻关系</h3>
            <input v-model="marriageForm.spouse_a_id" type="number" placeholder="成员 A ID" required />
            <input v-model="marriageForm.spouse_b_id" type="number" placeholder="成员 B ID" required />
            <input v-model="marriageForm.start_date" type="date" />
            <input v-model="marriageForm.end_date" type="date" />
            <select v-model="marriageForm.status">
              <option value="active">存续</option>
              <option value="ended">结束</option>
            </select>
            <button class="button button-primary" type="submit">
              <Plus class="icon-inline" />
              保存婚姻
            </button>
          </form>

          <form class="panel search-row" @submit.prevent="loadFamily">
            <input v-model="queryForm.family_member_id" type="number" placeholder="成员 ID" required />
            <button class="button button-primary" type="submit">
              <Search class="icon-inline" />
              查询配偶与子女
            </button>
          </form>

          <div v-if="family" class="panel relation-list">
            <h3>{{ family.member.name }}</h3>
            <p>配偶：{{ family.spouses.map((item) => item.name).join("、") || "无" }}</p>
            <p>子女：{{ family.children.map((item) => item.name).join("、") || "无" }}</p>
          </div>
        </section>

        <section v-if="activeTab === 'tree'" class="view-stack">
          <form class="panel search-row" @submit.prevent="loadTree">
            <input v-model="queryForm.tree_root_member_id" type="number" placeholder="根成员 ID" />
            <input v-model.number="queryForm.tree_max_depth" type="number" min="1" max="12" />
            <button class="button button-primary" type="submit">
              <GitBranch class="icon-inline" />
              预览
            </button>
          </form>
          <div class="panel">
            <p class="tree-hint">
              树形预览按页加载主体节点，每页最多显示 {{ treePageSize }} 个主体节点，并自动补齐到根节点的路径。
            </p>
            <div v-if="treeTotalNodes > 0" class="pagination-bar">
              <p class="pagination-summary">
                当前第 {{ treePage }} / {{ treeTotalPages }} 页，本页主体节点 {{ treePageNodes }} 个，
                当前层级范围总节点 {{ treeTotalNodes }} 个
              </p>
              <div class="pagination-actions">
                <button
                  class="button"
                  type="button"
                  :disabled="loading || !canLoadPreviousTreePage"
                  @click="loadPreviousTreePage"
                >
                  上一页
                </button>
                <label class="pagination-jump">
                  <span>跳至</span>
                  <input
                    v-model="treePageInput"
                    type="number"
                    min="1"
                    :max="treeTotalPages"
                    @keyup.enter="jumpToTreePage"
                  />
                </label>
                <button class="button" type="button" :disabled="loading" @click="jumpToTreePage">
                  跳转
                </button>
                <button
                  class="button"
                  type="button"
                  :disabled="loading || !canLoadNextTreePage"
                  @click="loadNextTreePage"
                >
                  下一页
                </button>
                <button
                  class="button"
                  type="button"
                  :disabled="loading || treePage === treeTotalPages"
                  @click="loadLastTreePage"
                >
                  最后一页
                </button>
              </div>
            </div>
            <ul class="tree-list">
              <TreeNodeView
                v-for="node in tree"
                :key="node.member.id"
                :node="node"
                @edit-member="openMemberEditorFromTree"
              />
            </ul>
          </div>
        </section>

        <section v-if="activeTab === 'ancestors'" class="view-stack">
          <form class="panel search-row" @submit.prevent="loadAncestors">
            <input v-model="queryForm.ancestor_member_id" type="number" placeholder="成员 ID" required />
            <button class="button button-primary" type="submit">
              <Network class="icon-inline" />
              查询祖先
            </button>
          </form>

          <form class="panel search-row" @submit.prevent="loadCommonAncestors">
            <input
              v-model="queryForm.common_ancestor_first_member_id"
              type="number"
              placeholder="成员 A ID"
              required
            />
            <input
              v-model="queryForm.common_ancestor_second_member_id"
              type="number"
              placeholder="成员 B ID"
              required
            />
            <button class="button button-primary" type="submit">
              <Network class="icon-inline" />
              查询最早共同祖先
            </button>
          </form>

          <div v-if="ancestorResultMode === 'single'" class="panel relation-list">
            <h3>祖先查询结果</h3>
            <p v-if="ancestors.length === 0" class="empty-hint">未找到祖先记录。</p>
            <article v-for="ancestor in ancestors" :key="ancestor.member.id" class="relation-item">
              <div class="relation-item__content">
                <strong>{{ ancestor.member.name }}</strong>
                <span>向上 {{ ancestor.depth }} 代</span>
                <span>{{ formatAncestorRoles(ancestor.parent_roles) }}</span>
                <span v-if="ancestor.path_count > 1">最近路径 {{ ancestor.path_count }} 条</span>
              </div>
              <button
                class="button"
                type="button"
                @click="openAncestorMemberDetail(ancestor.member)"
              >
                查看详情
              </button>
            </article>
          </div>

          <div v-if="ancestorResultMode === 'common'" class="panel relation-list">
            <h3>最早共同祖先</h3>
            <p v-if="commonAncestors.length === 0" class="empty-hint">未找到共同祖先。</p>
            <article
              v-for="ancestor in commonAncestors"
              :key="ancestor.member.id"
              class="relation-item"
            >
              <div class="relation-item__content">
                <strong>{{ ancestor.member.name }}</strong>
                <span>成员 A 向上 {{ ancestor.first_depth }} 代</span>
                <span>成员 B 向上 {{ ancestor.second_depth }} 代</span>
                <span>第 {{ ancestor.member.generation_index }} 代</span>
              </div>
              <button
                class="button"
                type="button"
                @click="openAncestorMemberDetail(ancestor.member)"
              >
                查看详情
              </button>
            </article>
          </div>

          <div v-if="selectedAncestorMember" class="panel member-detail-card">
            <h3>{{ selectedAncestorMember.name }}</h3>
            <div class="member-detail-grid">
              <p><strong>ID：</strong>{{ selectedAncestorMember.id }}</p>
              <p><strong>性别：</strong>{{ formatGender(selectedAncestorMember.gender) }}</p>
              <p><strong>代际：</strong>第 {{ selectedAncestorMember.generation_index }} 代</p>
              <p><strong>出生：</strong>{{ selectedAncestorMember.birth_date || "未录入" }}</p>
              <p><strong>逝世：</strong>{{ selectedAncestorMember.death_date || "未录入" }}</p>
              <p class="member-detail-biography">
                <strong>生平简介：</strong>{{ selectedAncestorMember.biography || "暂无简介" }}
              </p>
            </div>
          </div>
        </section>

        <section v-if="activeTab === 'relation'" class="view-stack">
          <form class="panel search-row" @submit.prevent="loadRelationshipPath">
            <input v-model="queryForm.source_member_id" type="number" placeholder="成员 A ID" required />
            <input v-model="queryForm.target_member_id" type="number" placeholder="成员 B ID" required />
            <button class="button button-primary" type="submit">
              <HeartHandshake class="icon-inline" />
              查询通路
            </button>
          </form>
          <div v-if="relationshipPath" class="panel relation-list">
            <h3>{{ relationshipPath.connected ? "存在亲缘通路" : "未找到亲缘通路" }}</h3>
            <div v-if="relationshipPath.connected" class="path-row">
              <span v-for="member in relationshipPath.path_members" :key="member.id">
                {{ member.name }} / {{ member.id }}
              </span>
            </div>
          </div>
        </section>

        <section v-if="activeTab === 'sql'" class="view-stack">
          <form class="panel search-row" @submit.prevent="runSelectedSqlQuery">
            <select v-model="selectedSqlQueryKey" @change="handleSqlQueryChange">
              <option v-for="query in sqlQueryDefinitions" :key="query.key" :value="query.key">
                {{ query.title }}
              </option>
            </select>
            <input
              v-if="selectedSqlNeedsMemberId"
              v-model="sqlQueryMemberId"
              type="number"
              placeholder="成员 ID"
              required
            />
            <button class="button button-primary" type="submit" :disabled="!selectedSqlDefinition">
              <ScrollText class="icon-inline" />
              执行查询
            </button>
          </form>

          <div v-if="selectedSqlDefinition" class="panel relation-list">
            <h3>{{ selectedSqlDefinition.title }}</h3>
            <p class="tree-hint">{{ selectedSqlDefinition.description }}</p>
            <pre class="sql-code"><code>{{ selectedSqlDefinition.sql }}</code></pre>
          </div>

          <div v-if="sqlQueryResult" class="panel table-wrap">
            <h3>{{ sqlQueryResult.title }}</h3>
            <table>
              <thead>
                <tr>
                  <th v-for="column in sqlQueryResult.columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in sqlQueryResult.rows" :key="`${sqlQueryResult.key}-${index}`">
                  <td v-for="column in sqlQueryResult.columns" :key="column">
                    {{ formatSqlCell(row[column]) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="sqlQueryResult.rows.length === 0" class="empty-hint">当前查询没有返回结果。</p>
          </div>
        </section>
      </section>
    </section>
  </main>
</template>
