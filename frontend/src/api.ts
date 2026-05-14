import type {
  AdminDashboardRead,
  AncestorRead,
  CommonAncestorRead,
  DashboardRead,
  FamilyRead,
  GenealogyRead,
  MemberListRead,
  MemberRead,
  RelationshipPathRead,
  SqlQueryDefinitionRead,
  SqlQueryResultRead,
  TokenResponse,
  TreePageRead,
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
    listSqlQueries: (genealogyId: number) =>
      request<SqlQueryDefinitionRead[]>(`/genealogies/${genealogyId}/sql-queries`),
    runSqlQuery: (
      genealogyId: number,
      payload: { query_key: string; member_id?: number },
    ) =>
      request<SqlQueryResultRead>(`/genealogies/${genealogyId}/sql-queries/run`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    listMembers: (
      genealogyId: number,
      options: { search: string; limit: number; offset: number },
    ) => {
      const params = new URLSearchParams({
        search: options.search,
        limit: String(options.limit),
        offset: String(options.offset),
      });
      return request<MemberListRead>(`/genealogies/${genealogyId}/members?${params.toString()}`);
    },
    createMember: (genealogyId: number, payload: Record<string, unknown>) =>
      request<MemberRead>(`/genealogies/${genealogyId}/members`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateMember: (memberId: number, payload: Record<string, unknown>) =>
      request<MemberRead>(`/members/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deleteMember: (memberId: number) =>
      request<void>(`/members/${memberId}`, {
        method: "DELETE",
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
    commonAncestors: (genealogyId: number, firstMemberId: string, secondMemberId: string) => {
      const params = new URLSearchParams({
        first_member_id: firstMemberId,
        second_member_id: secondMemberId,
      });
      return request<CommonAncestorRead[]>(
        `/genealogies/${genealogyId}/common-ancestors?${params.toString()}`,
      );
    },
    tree: (genealogyId: number, rootMemberId: string, maxDepth: number, page: number) => {
      const params = new URLSearchParams({ max_depth: String(maxDepth), page: String(page) });
      if (rootMemberId) {
        params.set("root_member_id", rootMemberId);
      }
      return request<TreePageRead>(`/genealogies/${genealogyId}/tree?${params.toString()}`);
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
