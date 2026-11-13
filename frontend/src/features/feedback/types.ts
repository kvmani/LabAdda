export type FeedbackCategory = "problem" | "suggestion" | "question";
export type FeedbackStatus = "new" | "seen" | "resolved";

export type FormFacts = {
  username: string;
  time: string;
  software_version: string;
  commit: string;
  max_message: number;
  max_files: number;
  max_file_bytes: number;
  max_total_bytes: number;
  email_copy: boolean;
};

export type MailState = {
  status: "none" | "queued" | "sent" | "failed";
  attempts: number;
  reason: string | null;
  sent_at: string | null;
  next_attempt_at: string | null;
  waiting_for_setup?: boolean;
};

export type FeedbackSummary = {
  id: string;
  created_at: string;
  username: string;
  category: FeedbackCategory;
  route: string | null;
  status: FeedbackStatus;
  attachment_count: number;
  email: MailState;
};

export type FeedbackAttachment = {
  id: string;
  display_name: string;
  media_type: string;
  size: number;
  url: string;
  preview_url: string | null;
};

export type FeedbackDetail = FeedbackSummary & {
  message: string;
  software_version: string;
  commit: string;
  user_agent: string | null;
  screen: string | null;
  admin_note: string | null;
  handled_at: string | null;
  revision: number;
  attachments: FeedbackAttachment[];
};

export type FeedbackPageData = {
  items: FeedbackSummary[];
  next_cursor: string | null;
  email: { configured: boolean; queued: number; failed: number };
};
