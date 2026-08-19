export type ResearchResourceSnapshot = {
  process_id: number;
  process_user_cpu_seconds: number;
  process_system_cpu_seconds: number;
  process_rss_bytes: number;
  process_rss_mib: number;
  system_memory_percent: number;
  system_cpu_percent: number;
  captured_at: string;
  scope: "dap-backend-process";
  research_specific_attribution: false;
  read_only: true;
  network_authority_granted: false;
  mutation_authority_granted: false;
  service_control_authority_granted: false;
};
