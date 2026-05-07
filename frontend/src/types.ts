export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: number;
  username: string;
  email: string;
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

export interface DashboardRead {
  genealogy_id: number;
  total_members: number;
  male_count: number;
  female_count: number;
  unknown_count: number;
}

export interface FamilyRead {
  member: MemberRead;
  spouses: MemberRead[];
  children: MemberRead[];
}

export interface AncestorRead {
  depth: number;
  parent_role: string;
  member: MemberRead;
}

export interface TreeNode {
  member: MemberRead;
  depth: number;
  children: TreeNode[];
}

export interface RelationshipPathRead {
  connected: boolean;
  path_members: MemberRead[];
  relation_steps: string[];
  depth: number;
}
