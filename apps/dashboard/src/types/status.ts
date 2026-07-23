export type SystemStatus = {
  timestamp: string;
  system: {
    cpu: {
      usage_percent: number;
      physical_cores: number | null;
      logical_threads: number | null;
    };
    memory: {
      total_gb: number;
      used_gb: number;
      available_gb: number;
      percent: number;
    };
    uptime: {
      seconds: number;
      formatted: string;
    };
    disks: {
      system: {
        path: string;
        total_gb: number;
        used_gb: number;
        free_gb: number;
        percent: number;
      };
    };
  };
  ollama: {
    online: boolean;
    loaded_count: number;
    loaded_models: Array<{
      name: string | null;
      size: number | null;
      size_vram: number | null;
      expires_at: string | null;
    }>;
    error?: string;
  };
};