import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { SYSTEM_STATUS } from '../../utils/constants'

const variants = {
  success: 'bg-green-100 text-green-800',
  warning: 'bg-amber-100 text-amber-800',
  danger: 'bg-red-100 text-red-800',
  info: 'bg-blue-100 text-blue-800',
  default: 'bg-gray-100 text-gray-800',
}

function StatusBadge({ status, variant = 'default', children, className }) {
  const { t } = useTranslation()

  const statusConfig = {
    [SYSTEM_STATUS.IDLE]: { variant: 'default', text: t('status.idle') },
    [SYSTEM_STATUS.CONNECTING]: { variant: 'info', text: t('status.connecting') },
    [SYSTEM_STATUS.CONNECTED]: { variant: 'success', text: t('status.connected') },
    [SYSTEM_STATUS.RUNNING]: { variant: 'success', text: t('status.running') },
    [SYSTEM_STATUS.PAUSED]: { variant: 'warning', text: t('status.paused') },
    [SYSTEM_STATUS.STOPPED]: { variant: 'default', text: t('status.stopped') },
    [SYSTEM_STATUS.ERROR]: { variant: 'danger', text: t('status.error') },
  }

  const config = status ? statusConfig[status] : null
  const finalVariant = config?.variant || variant
  const finalText = config?.text || children

  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[finalVariant],
        className
      )}
    >
      {finalText}
    </span>
  )
}

export default StatusBadge
