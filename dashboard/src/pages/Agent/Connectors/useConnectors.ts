import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import {
  connectorsApi,
  type ConnectorCatalogEntry,
  type ConnectorInstance,
} from "../../../api/modules/connectors";
import { useAsyncResource } from "../../../hooks/useAsyncResource";

const EMPTY = {
  catalog: [] as ConnectorCatalogEntry[],
  instances: [] as ConnectorInstance[],
};

export function useConnectorInstances() {
  const { t } = useTranslation();

  const { data, loading, refresh, setData } = useAsyncResource(
    EMPTY,
    async () => {
      const [cat, inst] = await Promise.all([
        connectorsApi.catalog(),
        connectorsApi.listInstances(),
      ]);
      return { catalog: cat ?? [], instances: inst ?? [] };
    },
    [],
    { errorFallback: t("connectors.loadFailed"), t, logLabel: "Connectors" },
  );

  useEffect(() => {
    if (import.meta.env.VITE_VOS !== "1") return;
    const timer = setInterval(() => {
      void connectorsApi
        .listInstances()
        .then((instances) => {
          setData((previous) => ({ ...previous, instances }));
        })
        .catch(() => undefined);
    }, 15000);
    return () => clearInterval(timer);
  }, [setData]);

  return {
    catalog: data.catalog,
    instances: data.instances,
    loading,
    refresh,
  };
}
