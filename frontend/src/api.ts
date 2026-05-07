import type {
  AdminDashboardRead,
  AncestorRead,
  DashboardRead,
  FamilyRead,
  GenealogyRead,
  MemberRead,
  RelationshipPathRead,
  TokenResponse,
  TreeNode,
  UserRead,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface ApiClientOptions {
  getBaseUrl: () => string;
  getToken: () => string;
}

export function createApiClient(options: ApiClientOptions) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    const token = options.getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${options.getBaseUrl()}${path}`, {
      ...init,
      headers,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(response.status, body.detail ?? "请求失败");
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  return {
    login: (email: string, password: string) =>
      request<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    register: (username: string, email: string, password: string) =>
      request<TokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      }),
    me: () => request<UserRead>("/me"),
    adminDashboard: () => request<AdminDashboardRead>("/admin/dashboard"),
    listGenealogies: () => request<GenealogyRead[]>("/genealogies"),
    createGenealogy: (payload: {
      name: string;
      surname: string;
      revision_time: string | null;
    }) =>
      request<GenealogyRead>("/genealogies", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    inviteCollaborator: (genealogyId: number, email: string, role: string) =>
      request<{ genealogy_id: number; user_id: number; role: string }>(
        `/genealogies/${genealogyId}/invite`,
        {
          method: "POST",
          body: JSON.stringify({ email, role }),
        },
      ),
    dashboard: (genealogyId: number) =>
      request<DashboardRead>(`/genealogies/${genealogyId}/dashboard`),
    listMembers: (genealogyId: number, search: string) =>
      request<MemberRead[]>(
        `/genealogies/${genealogyId}/members?search=${encodeURIComponent(search)}`,
      ),
    createMember: (genealogyId: number, payload: Record<string, unknown>) =>
      request<MemberRead>(`/genealogies/${genealogyId}/members`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createParentChild: (genealogyId: number, payload: Record<string, unknown>) =>
      request<{ id: number }>(`/genealogies/${genealogyId}/relations/parent-child`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createMarriage: (genealogyId: number, payload: Record<string, unknown>) =>
      request<{ id: number }>(`/genealogies/${genealogyId}/marriages`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    family: (memberId: number) => request<FamilyRead>(`/members/${memberId}/family`),
    ancestors: (memberId: number) =>
      request<AncestorRead[]>(`/members/${memberId}/ancestors`),
    tree: (genealogyId: number, rootMemberId: string, maxDepth: number) => {
      const params = new URLSearchParams({ max_depth: String(maxDepth) });
      if (rootMemberId) {
        params.set("root_member_id", rootMemberId);
      }
      return request<TreeNode[]>(`/genealogies/${genealogyId}/tree?${params.toString()}`);
    },
    relationshipPath: (genealogyId: number, sourceMemberId: string, targetMemberId: string) => {
      const params = new URLSearchParams({
        source_member_id: sourceMemberId,
        target_member_id: targetMemberId,
      });
      return request<RelationshipPathRead>(
        `/genealogies/${genealogyId}/relationship-path?${params.toString()}`,
      );
    },
  };
}
