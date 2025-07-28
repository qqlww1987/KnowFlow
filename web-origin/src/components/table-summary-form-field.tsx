import { useTranslate } from '@/hooks/common-hooks';
import { useFormContext } from 'react-hook-form';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from './ui/form';
import { Switch } from './ui/switch';

export function TableSummaryFormField() {
  const form = useFormContext();
  const { t } = useTranslate('knowledgeDetails');

  return (
    <FormField
      control={form.control}
      name="parser_config.enable_table_summary"
      render={({ field }) => (
        <FormItem defaultChecked={false}>
          <FormLabel tooltip={t('tableSummaryTip')}>
            {t('tableSummary')}
          </FormLabel>
          <FormControl>
            <Switch
              checked={field.value}
              onCheckedChange={field.onChange}
            ></Switch>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
} 