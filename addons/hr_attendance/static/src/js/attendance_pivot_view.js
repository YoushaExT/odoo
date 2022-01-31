import { registry } from "@web/core/registry";
import { PivotView } from "@web/views/pivot/pivot_view";

const viewRegistry = registry.category("views");

class AttendancePivotView extends PivotView {}
console.log('++++++')

viewRegistry.add("attendance_pivot", AttendancePivotView);
