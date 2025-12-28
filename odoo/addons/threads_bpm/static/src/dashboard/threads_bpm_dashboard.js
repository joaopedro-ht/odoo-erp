/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ThreadsBPMDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            executions: null,
            stats: null,
        });

        onWillStart(async () => {
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        try {
            this.state.executions = await this.orm.call("threads_bpm.execution", "get_user_executions", [], {});
            this.state.stats = this._calculateStats();
        } finally {
            this.state.loading = false;
        }
    }

    _calculateStats() {
        if (!this.state.executions) return null;

        const executions = this.state.executions;
        const total = executions.on_track.length + executions.at_risk.length + executions.overdue.length + executions.completed.length;

        return {
            total: total,
            on_track: executions.on_track.length,
            at_risk: executions.at_risk.length,
            overdue: executions.overdue.length,
            completed: executions.completed.length,
        };
    }

    openExecutions(filter = null) {
        let domain = [];
        if (filter === 'on_track') {
            domain = [['state', '=', 'in_progress'], ['has_overdue_steps', '=', false], ['has_at_risk_steps', '=', false]];
        } else if (filter === 'at_risk') {
            domain = [['state', '=', 'in_progress'], ['has_at_risk_steps', '=', true], ['has_overdue_steps', '=', false]];
        } else if (filter === 'overdue') {
            domain = [['state', '=', 'in_progress'], ['has_overdue_steps', '=', true]];
        } else if (filter === 'completed') {
            domain = [['state', '=', 'completed']];
        }

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Execuções',
            res_model: 'threads_bpm.execution',
            view_mode: 'tree,form',
            domain: domain,
            context: {},
        });
    }

    openTemplates() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Modelos',
            res_model: 'threads_bpm.template',
            view_mode: 'tree,form',
            context: {},
        });
    }

    createExecution() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Nova Execução',
            res_model: 'threads_bpm.execution',
            view_mode: 'form',
            context: {},
            target: 'new',
        });
    }

    createTemplate() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Novo Modelo',
            res_model: 'threads_bpm.template',
            view_mode: 'form',
            context: {},
            target: 'new',
        });
    }

    openExecution(executionId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Execução',
            res_model: 'threads_bpm.execution',
            res_id: executionId,
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
        });
    }

    getStatusBadgeClass(status) {
        const classes = {
            'on_track': 'badge bg-success',
            'at_risk': 'badge bg-warning text-dark',
            'overdue': 'badge bg-danger',
            'completed': 'badge bg-secondary'
        };
        return classes[status] || 'badge bg-light text-dark';
    }

    getStatusText(status) {
        const texts = {
            'on_track': 'Em Dia',
            'at_risk': 'Em Risco',
            'overdue': 'Atrasada',
            'completed': 'Concluída'
        };
        return texts[status] || status;
    }

    getExecutionStatus(execution) {
        if (execution.state === 'completed') return 'completed';
        if (execution.has_overdue_steps) return 'overdue';
        if (execution.has_at_risk_steps) return 'at_risk';
        return 'on_track';
    }
}

ThreadsBPMDashboard.template = "threads_bpm.Dashboard";

registry.category("actions").add("threads_bpm.dashboard", ThreadsBPMDashboard);
