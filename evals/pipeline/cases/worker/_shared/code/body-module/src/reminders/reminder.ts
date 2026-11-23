export type Reminder = {
  id: string;
  title: string;
  dueAt: string;
  status: "open" | "done";
};
