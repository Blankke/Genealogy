<script setup lang="ts">
import {
  GitBranch,
  HeartHandshake,
  LogOut,
  Network,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
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
  DashboardRead,
  FamilyRead,
  GenealogyRead,
  MemberRead,
  RelationshipPathRead,
  TreeNode,
  UserRead,
} from "./types";

type TabKey = "admin" | "dashboard" | "members" | "tree" | "ancestors" | "relation";
type AuthMode = "login" | "register";

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
const family = ref<FamilyRead | null>(null);
const ancestors = ref<AncestorRead[]>([]);
const tree = ref<TreeNode[]>([]);
const relationshipPath = ref<RelationshipPathRead | null>(null);

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

const queryForm = reactive({
  family_member_id: "",
  tree_root_member_id: "",
  tree_max_depth: 5,
  ancestor_member_id: "",
  source_member_id: "",
  target_member_id: "",
});

const tabs = [
  { key: "dashboard", label: "概览", icon: ShieldCheck },
  { key: "members", label: "成员", icon: Users },
  { key: "tree", label: "树形", icon: GitBranch },
  { key: "ancestors", label: "祖先", icon: Network },
  { key: "relation", label: "亲缘", icon: HeartHandshake },
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

function formatGender(gender: string) {
  return { male: "男", female: "女", unknown: "未知" }[gender] ?? gender;
}

function normalizeDate(value: string) {
  return value || null;
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
    members.value = await api.listMembers(selectedGenealogyId.value, memberSearch.value);
  }
  if (activeTab.value === "tree") {
    tree.value = await api.tree(
      selectedGenealogyId.value,
      queryForm.tree_root_member_id,
      queryForm.tree_max_depth,
    );
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

async function searchMembers() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    members.value = await api.listMembers(selectedGenealogyId.value!, memberSearch.value);
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
    await searchMembers();
  }, "成员已创建");
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

async function loadFamily() {
  await runTask(async () => {
    family.value = await api.family(Number(queryForm.family_member_id));
  });
}

async function loadTree() {
  if (!selectedGenealogyId.value) return;
  await runTask(async () => {
    tree.value = await api.tree(
      selectedGenealogyId.value!,
      queryForm.tree_root_member_id,
      queryForm.tree_max_depth,
    );
  });
}

async function loadAncestors() {
  await runTask(async () => {
    ancestors.value = await api.ancestors(Number(queryForm.ancestor_member_id));
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
          <select v-model.number="selectedGenealogyId" @change="refreshCurrentView">
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
            <input v-model="memberSearch" placeholder="按姓名模糊查找" />
            <button class="button button-primary" type="submit">
              <Search class="icon-inline" />
              查找
            </button>
          </form>

          <div class="panel table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>姓名</th>
                  <th>性别</th>
                  <th>生年</th>
                  <th>卒年</th>
                  <th>辈分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in members" :key="member.id">
                  <td>{{ member.id }}</td>
                  <td>{{ member.name }}</td>
                  <td>{{ formatGender(member.gender) }}</td>
                  <td>{{ member.birth_date || "-" }}</td>
                  <td>{{ member.death_date || "-" }}</td>
                  <td>{{ member.generation_index }}</td>
                </tr>
              </tbody>
            </table>
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
            <h3>亲子关系</h3>
            <input v-model="parentChildForm.parent_id" type="number" placeholder="父/母 ID" required />
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
            <h3>婚姻关系</h3>
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
              配偶与子女
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
            <ul class="tree-list">
              <TreeNodeView v-for="node in tree" :key="node.member.id" :node="node" />
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
          <div class="panel relation-list">
            <article v-for="ancestor in ancestors" :key="ancestor.member.id" class="relation-item">
              <strong>{{ ancestor.member.name }}</strong>
              <span>向上 {{ ancestor.depth }} 代</span>
              <span>{{ ancestor.parent_role === "father" ? "父系" : "母系" }}</span>
            </article>
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
      </section>
    </section>
  </main>
</template>
