export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface GenealogyRead {
  id: number;
  name: string;
  surname: string;
  revision_time: string | null;
  owner_user_id: number;
  created_at: string;
}

export interface MemberRead {
  id: number;
  genealogy_id: number;
  name: string;
  gender: "male" | "female" | "unknown";
  birth_date: string | null;
  death_date: string | null;
  generation_index: number;
  biography: string;
  created_at: string;
}

export interface MemberListRead {
  items: MemberRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardRead {
  genealogy_id: number;
  total_members: number;
  male_count: number;
  female_count: number;
  unknown_count: number;
}

export interface AdminDashboardRead {
  total_users: number;
  total_genealogies: number;
  total_members: number;
  male_count: number;
  female_count: number;
  unknown_count: number;
  total_parent_child_relations: number;
  total_marriages: number;
}

export interface FamilyRead {
  member: MemberRead;
  spouses: MemberRead[];
  children: MemberRead[];
}

export interface AncestorRead {
  depth: number;
  parent_role: string;
  parent_roles: string[];
  path_count: number;
  member: MemberRead;
}

export interface CommonAncestorRead {
  first_depth: number;
  second_depth: number;
  member: MemberRead;
}

export interface SqlQueryDefinitionRead {
  key: string;
  title: string;
  description: string;
  sql: string;
  required_params: string[];
}

export interface SqlQueryResultRead {
  key: string;
  title: string;
  description: string;
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface TreeNode {
  member: MemberRead;
  depth: number;
  children: TreeNode[];
}

export interface TreePageRead {
  items: TreeNode[];
  page: number;
  page_size: number;
  page_nodes: number;
  total_nodes: number;
  total_pages: number;
}

export interface RelationshipPathRead {
  connected: boolean;
  path_members: MemberRead[];
  relation_steps: string[];
  depth: number;
}
