export type JoinRequestItem = {
  id: string;
  created_at: string;
  full_name: string;
  username: string;
  employee_no: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  designation: string | null;
  unit_id: string | null;
  unit_name: string | null;
  statement_of_interest: string | null;
  status: "pending" | "approved" | "rejected";
  reviewed_at: string | null;
  reviewed_by: string | null;
  review_note: string | null;
  created_user_id: string | null;
};

export type JoinRequestsResponse = {
  requests: JoinRequestItem[];
  next_offset: number | null;
  counts: {
    pending: number;
    approved: number;
    rejected: number;
    total: number;
  };
};

export type ApprovedSlip = {
  code: string;
  expires_at: string;
  fullName: string;
  username: string;
};

export type FilterStatus = "all" | "pending" | "approved" | "rejected";
