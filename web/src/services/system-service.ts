import api from '@/utils/api';
import { get } from '@/utils/request';

const systemService = {
  getSystemStatus: () => {
    return get(api.getSystemStatus);
  },
  getSystemConfig: () => {
    return get(api.getSystemConfig);
  },
};

export default systemService;
