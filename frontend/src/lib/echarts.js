// 仅注册项目实际使用的雷达图能力，避免把完整 ECharts 打进首个 chunk。
import { RadarChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([RadarChart, TooltipComponent, CanvasRenderer])

export { init } from 'echarts/core'
