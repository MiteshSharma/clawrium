import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSkills() {
  return useQuery({
    queryKey: ["skills"],
    queryFn: api.getSkills,
  });
}

export function useSkill(registry: string | null, name: string | null) {
  return useQuery({
    queryKey: ["skill", registry, name],
    queryFn: () => api.getSkill(registry as string, name as string),
    enabled: !!registry && !!name,
  });
}
