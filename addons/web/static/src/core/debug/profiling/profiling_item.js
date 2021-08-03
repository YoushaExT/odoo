/** @odoo-module **/

import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useBus, useService } from "@web/core/utils/hooks";

const { Component } = owl;

export class ProfilingItem extends Component {
    setup() {
        this.profiling = useService("profiling");
        useBus(this.props.bus, "UPDATE", this.render);
    }

    changeParam(param, ev) {
        this.profiling.setParam(param, ev.target.value);
    }
    openProfiles() {
        if (this.env.services.action) {
            // using doAction in the backend to preserve breadcrumbs and stuff
            this.env.services.action.doAction("base.action_menu_ir_profile");
        } else {
            // No action service means we are in the frontend.
            window.location = "/web/#action=base.action_menu_ir_profile";
        }
    }
}
ProfilingItem.components = { DropdownItem };
ProfilingItem.template = "web.DebugMenu.ProfilingItem";
