/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {scanBarcode} from "@web/webclient/barcode/barcode_scanner";
import {useService} from "@web/core/utils/hooks";

export class BarcodeInterface extends Component {
    static template = "stock_barcode_oca.BarcodeInterface";

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.barcodeService = useService("barcode");
        this.orm = useService("orm");
        this.stepsContainerRef = useRef("stepsContainer");

        this.state = useState({
            pickingId: this.props.action.context.active_id,
            profileId: this.props.action.context.barcode_profile_id,
            pickingName: "",
            partnerName: "",
            moveLines: [],

            profileConfig: {
                scanning_sequence: [],
                has_initial_step: false,
                has_final_step: false,
                cyclic_steps_count: 0,
            },

            currentStepId: null,
            currentStep: null,
            currentStepType: null,
            allowedTargetTypes: [],

            scanInstructions: "",
            lastScannedCode: "",
            lastScanSuccess: null,
            lastScanTimestamp: null,

            currentContext: {
                product_id: null,
                product_name: null,
                lot_id: null,
                lot_name: null,
                serial_id: null,
                serial_name: null,
                source_location_id: null,
                source_location_name: null,
                destination_location_id: null,
                destination_location_name: null,
                package_id: null,
                package_name: null,
                picked_quantities: {},
            },

            completedSteps: [],
            totalQty: 0,
            pickedQty: 0,
            inCyclicFlow: false,
            sequenceCompleted: false,

            showChatter: false,
            chatterMessage: "",
            chatterAttachments: [],
            showMentionList: false,
            mentionableUsers: [],
            mentionedPartners: [],
            mentionSearchText: "",

            showBackorderDialog: false,
            backorderPendingLines: [],
        });

        onWillStart(async () => {
            await Promise.all([this._loadPickingData(), this._loadProfileConfig()]);

            if (this.state.profileConfig.scanning_sequence.length > 0) {
                await this._loadBackendState();
                this._initializeScanningSequence();
            }
        });

        onMounted(() => {
            this.barcodeService.bus.addEventListener(
                "barcode_scanned",
                this._onBarcodeScanned
            );
            this._detectStepWraps();
        });

        onPatched(() => {
            this._detectStepWraps();
        });

        onWillUnmount(() => {
            if (this.state.currentStepId && !this.state.sequenceCompleted) {
                this._syncStateToBackend();
            }

            this.barcodeService.bus.removeEventListener(
                "barcode_scanned",
                this._onBarcodeScanned
            );
        });
    }

    async _loadPickingData() {
        const picking = await this.orm.read(
            "stock.picking",
            [this.state.pickingId],
            ["name", "partner_id", "move_ids"]
        );
        if (picking && picking.length > 0) {
            this.state.pickingName = picking[0].name;
            this.state.partnerName = picking[0].partner_id
                ? picking[0].partner_id[1]
                : "";
            if (picking[0].move_ids && picking[0].move_ids.length > 0) {
                const moves = await this.orm.read("stock.move", picking[0].move_ids, [
                    "product_id",
                    "product_uom_qty",
                    "quantity",
                    "product_uom",
                    "move_line_ids",
                ]);
                const productIds = [...new Set(moves.map((m) => m.product_id[0]))];
                const products = await this.orm.read("product.product", productIds, [
                    "name",
                    "default_code",
                    "tracking",
                ]);
                const productMap = {};
                products.forEach((p) => {
                    productMap[p.id] = p;
                });

                // Leer move_lines para calcular qty_picked y detectar lotes únicos
                const allMoveLineIds = moves.flatMap((m) => m.move_line_ids || []);
                const pickedByMove = {};
                const moveLineLotsByMove = {};

                if (allMoveLineIds.length > 0) {
                    const moveLines = await this.orm.read(
                        "stock.move.line",
                        allMoveLineIds,
                        ["move_id", "qty_picked", "lot_id"]
                    );

                    // Agrupar por move y sumar qty_picked, detectar lotes
                    moveLines.forEach((ml) => {
                        const moveId = ml.move_id[0];
                        pickedByMove[moveId] =
                            (pickedByMove[moveId] || 0) + ml.qty_picked;

                        // Rastrear lotes únicos por move (para visibilidad de botones)
                        if (!moveLineLotsByMove[moveId]) {
                            moveLineLotsByMove[moveId] = [];
                        }
                        if (ml.lot_id && ml.lot_id[0]) {
                            if (!moveLineLotsByMove[moveId].includes(ml.lot_id[0])) {
                                moveLineLotsByMove[moveId].push(ml.lot_id[0]);
                            }
                        }
                    });
                }

                this.state.moveLines = moves.map((move) => ({
                    id: move.id,
                    product_id: move.product_id[0],
                    product_uom: move.product_uom[1],
                    product_name: productMap[move.product_id[0]].name,
                    product_code: productMap[move.product_id[0]].default_code || "",
                    quantity_demand: move.product_uom_qty,
                    qty_picked: pickedByMove[move.id] || 0,
                    quantity_reserved: move.quantity,
                    tracking: productMap[move.product_id[0]].tracking,
                    unique_lot_count: (moveLineLotsByMove[move.id] || []).length,
                }));

                // Calcular progreso por cantidades, no por líneas
                this.state.totalQty = this.state.moveLines.reduce(
                    (sum, m) => sum + m.quantity_demand,
                    0
                );
                this.state.pickedQty = this.state.moveLines.reduce(
                    (sum, m) => sum + m.qty_picked,
                    0
                );
            }
        }
    }

    async _loadProfileConfig() {
        if (!this.state.profileId) {
            return;
        }
        try {
            const config = await this.orm.call(
                "stock.barcode.app.profile",
                "get_interface_config",
                [[this.state.profileId]]
            );
            this.state.profileConfig = config;
        } catch (error) {
            this.notification.add("Could not load profile configuration", {
                type: "warning",
            });
        }
    }

    async _loadBackendState() {
        try {
            const picking = await this.orm.read(
                "stock.picking",
                [this.state.pickingId],
                ["barcode_scan_state"]
            );

            if (picking && picking[0].barcode_scan_state) {
                const backendState = JSON.parse(picking[0].barcode_scan_state);
                if (backendState.scanned_context) {
                    Object.assign(
                        this.state.currentContext,
                        backendState.scanned_context
                    );
                }
                if (backendState.completed_steps) {
                    this.state.completedSteps = backendState.completed_steps;
                }
                if (backendState.current_step_id) {
                    this.state.currentStepId = backendState.current_step_id;
                }
            }
        } catch (error) {
            console.error("Error loading backend state:", error);
        }
    }

    _initializeScanningSequence() {
        if (
            this.state.currentStepId === null ||
            this.state.currentStepId === undefined
        ) {
            const initialStep = this.state.profileConfig.scanning_sequence.find(
                (s) => s.step_type === "initial"
            );
            if (initialStep) {
                this._updateCurrentStep({
                    step: initialStep,
                    instructions: this._generateLocalInstructions(initialStep),
                    applicable_targets: initialStep.targets,
                });
            } else if (this.state.profileConfig.scanning_sequence.length > 0) {
                const firstStep = this.state.profileConfig.scanning_sequence[0];
                this._updateCurrentStep({
                    step: firstStep,
                    instructions: this._generateLocalInstructions(firstStep),
                    applicable_targets: firstStep.targets,
                });
            }
        } else {
            const currentStep = this.state.profileConfig.scanning_sequence.find(
                (s) => s.id === this.state.currentStepId
            );
            if (currentStep) {
                this._updateCurrentStep({
                    step: currentStep,
                    instructions: this._generateLocalInstructions(currentStep),
                    applicable_targets: currentStep.targets,
                });
            }
        }
    }

    _updateCurrentStep(stepInfo) {
        if (stepInfo.step) {
            this.state.currentStepId = stepInfo.step.id;
            this.state.currentStep = stepInfo.step;
            this.state.currentStepType = stepInfo.step.step_type;
            this.state.allowedTargetTypes = stepInfo.applicable_targets.map(
                (t) => t.technical_name
            );
            this.state.scanInstructions = stepInfo.instructions;

            if (stepInfo.step.step_type === "cyclic") {
                this.state.inCyclicFlow = true;
            }
        } else {
            this.state.currentStepId = null;
            this.state.currentStep = null;
            this.state.currentStepType = null;
            this.state.allowedTargetTypes = [];
            this.state.scanInstructions = "Scanning sequence completed";
            this.state.sequenceCompleted = true;
            this.state.inCyclicFlow = false;
        }
    }

    _generateLocalInstructions(step) {
        if (!step || !step.targets || step.targets.length === 0) {
            return "Continue scanning";
        }

        // Simple fallback - backend generates better instructions
        const targetNames = step.targets.map((t) => t.display_name);
        const instruction =
            targetNames.length === 1
                ? `Scan ${targetNames[0]}`
                : `Scan ${targetNames.join(" or ")}`;

        return instruction;
    }

    _markStepCompleted(stepId) {
        if (!this.state.completedSteps.includes(stepId)) {
            this.state.completedSteps.push(stepId);
        }
    }

    async _syncStateToBackend() {
        try {
            await this.orm.write("stock.picking", [this.state.pickingId], {
                barcode_scan_state: JSON.stringify({
                    current_step_id: this.state.currentStepId,
                    current_step_type: this.state.currentStepType,
                    scanned_context: this.state.currentContext,
                    completed_steps: this.state.completedSteps,
                }),
            });
        } catch (error) {
            console.error("Error syncing state to backend:", error);
        }
    }

    _onBarcodeScanned = (ev) => {
        const barcode = ev.detail.barcode;
        if (barcode) {
            this._processBarcode(barcode);
        }
    };

    async _processBarcode(barcode) {
        this.state.lastScannedCode = barcode;
        this.state.lastScanTimestamp = Date.now();

        try {
            const result = await this.orm.call(
                "stock.picking",
                "process_scanned_barcode",
                [[this.state.pickingId], barcode]
            );

            this.state.lastScanSuccess = result.success;

            if (result.success) {
                if ("vibrate" in window.navigator) {
                    window.navigator.vibrate(100);
                }

                if (result.scanned_data) {
                    Object.assign(this.state.currentContext, result.scanned_data);
                }

                if (result.next_step_info) {
                    this._updateCurrentStep(result.next_step_info);
                }

                if (result.scan_instructions) {
                    this.state.scanInstructions = result.scan_instructions;
                }

                if (result.move_id && result.quantity_to_add) {
                    // Recargar datos desde BD para actualizar qty_picked
                    await this._loadPickingData();
                }

                if (result.completed_step_id) {
                    this._markStepCompleted(result.completed_step_id);
                }

                if (result.sequence_completed) {
                    this.state.sequenceCompleted = true;
                    this.notification.add("Operation completed!", {
                        type: "success",
                        title: "Success",
                    });
                }

                this.notification.add(result.message, {type: "success"});
            } else {
                if ("vibrate" in window.navigator) {
                    window.navigator.vibrate([100, 50, 100]);
                }

                this.notification.add(result.message, {type: "warning"});
            }
        } catch (error) {
            this.state.lastScanSuccess = false;
            console.error("Error processing barcode:", error);
            this.notification.add("Error processing barcode", {
                type: "danger",
            });
        }
    }

    onClose() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.picking",
            res_id: this.state.pickingId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onScanWithCamera() {
        try {
            const barcode = await scanBarcode(this.env);
            if (barcode) {
                await this._processBarcode(barcode);
            }
        } catch (error) {
            this.notification.add(error.message, {type: "warning"});
        }
    }

    async onIncrementQty(moveId, amount) {
        try {
            const result = await this.orm.call("stock.move", "increment_qty_picked", [
                [moveId],
                amount,
            ]);

            if (result.success) {
                await this._loadPickingData();
                this.notification.add(result.message || "Quantity updated", {
                    type: "success",
                });
            } else {
                this.notification.add(result.message || "Failed to update quantity", {
                    type: "warning",
                });
            }
        } catch (error) {
            console.error("Error incrementing quantity:", error);
            this.notification.add("Error updating quantity", {type: "danger"});
        }
    }

    async onForceStep(stepId) {
        try {
            const step = this.state.profileConfig.scanning_sequence.find(
                (s) => s.id === stepId
            );
            if (step) {
                this._updateCurrentStep({
                    step: step,
                    instructions: this._generateLocalInstructions(step),
                    applicable_targets: step.targets,
                });

                await this._syncStateToBackend();
                this.notification.add(`Switched to step: ${step.name}`, {type: "info"});
            }
        } catch (error) {
            console.error("Error forcing step:", error);
            this.notification.add("Error changing step", {type: "danger"});
        }
    }

    canShowIncrementButtons(line) {
        if (line.tracking === "none") {
            return true;
        }
        if (line.tracking === "serial") {
            return false;
        }
        if (line.tracking === "lot") {
            return line.unique_lot_count === 1;
        }
        return false;
    }

    showPlusOne(line) {
        return (
            this.canShowIncrementButtons(line) && line.qty_picked < line.quantity_demand
        );
    }

    showMinusOne(line) {
        return this.canShowIncrementButtons(line) && line.qty_picked > 0;
    }

    showPlusRemainder(line) {
        return (
            this.canShowIncrementButtons(line) && line.qty_picked < line.quantity_demand
        );
    }

    getRemainder(line) {
        return line.quantity_demand - line.qty_picked;
    }

    _detectStepWraps() {
        if (!this.stepsContainerRef.el) return;

        const steps = this.stepsContainerRef.el.querySelectorAll(".step_block");
        if (steps.length <= 1) return;

        // Detectar qué steps están en la misma línea
        let previousTop = null;
        let lineSteps = [];

        steps.forEach((step, index) => {
            const rect = step.getBoundingClientRect();
            const currentTop = rect.top;

            // Reset clases
            step.classList.remove(
                "step_has_next",
                "step_has_prev",
                "step_line_start",
                "step_line_end"
            );

            if (previousTop === null || Math.abs(currentTop - previousTop) < 5) {
                // Misma línea
                lineSteps.push(step);
            } else {
                // Nueva línea - procesar línea anterior
                this._applyLineClasses(lineSteps);
                lineSteps = [step];
            }

            previousTop = currentTop;

            // Última iteración
            if (index === steps.length - 1) {
                this._applyLineClasses(lineSteps);
            }
        });
    }

    _applyLineClasses(lineSteps) {
        if (lineSteps.length === 0) return;

        if (lineSteps.length === 1) {
            // Step solo en su línea - sin polygon
            lineSteps[0].classList.add("step_line_start", "step_line_end");
        } else {
            // Múltiples steps en la línea
            lineSteps.forEach((step, index) => {
                if (index === 0) {
                    step.classList.add("step_line_start", "step_has_next");
                } else if (index === lineSteps.length - 1) {
                    step.classList.add("step_line_end", "step_has_prev");
                } else {
                    step.classList.add("step_has_prev", "step_has_next");
                }
            });
        }
    }

    async onValidate() {
        try {
            // Validar que tenga productos pickeados
            if (this.state.pickedQty === 0) {
                this.notification.add("No products have been picked yet", {
                    type: "warning",
                });
                return;
            }

            // Llamar a button_validate y capturar la respuesta
            const result = await this.orm.call("stock.picking", "button_validate", [
                this.state.pickingId,
            ]);

            // Si result es un objeto con res_model, es un wizard
            if (
                result &&
                typeof result === "object" &&
                result.res_model === "stock.backorder.confirmation"
            ) {
                // Mostrar el diálogo de backorder personalizado
                await this._showBackorderDialog();
            } else {
                // Validación exitosa directa
                this.notification.add("Picking validated successfully", {
                    type: "success",
                });
                // Volver al formulario del picking
                this.onClose();
            }
        } catch (error) {
            console.error("Error validating picking:", error);
            this.notification.add(error.message || "Error validating picking", {
                type: "danger",
            });
        }
    }

    async onToggleChatter() {
        this.state.showChatter = !this.state.showChatter;

        if (this.state.showChatter) {
            // Cargar usuarios mencionables al abrir
            await this._loadMentionableUsers();
        } else {
            // Limpiar al cerrar
            this.state.chatterMessage = "";
            this.state.chatterAttachments = [];
            this.state.showMentionList = false;
            this.state.mentionedPartners = [];
            this.state.mentionSearchText = "";
        }
    }

    onCloseChatter() {
        this.state.showChatter = false;
        this.state.chatterMessage = "";
        this.state.chatterAttachments = [];
        this.state.showMentionList = false;
        this.state.mentionedPartners = [];
        this.state.mentionSearchText = "";
    }

    async _loadMentionableUsers() {
        try {
            // Obtener todos los usuarios internos (share=False)
            const users = await this.orm.searchRead(
                "res.users",
                [
                    ["share", "=", false],
                    ["active", "=", true],
                ],
                ["name", "partner_id"]
            );

            this.state.mentionableUsers = users.map((u) => ({
                id: u.partner_id[0],
                name: u.name,
            }));
        } catch (error) {
            console.error("Error loading mentionable users:", error);
            this.state.mentionableUsers = [];
        }
    }

    onOpenMentionList() {
        this.state.showMentionList = !this.state.showMentionList;
        if (this.state.showMentionList) {
            this.state.mentionSearchText = "";
        }
    }

    getFilteredMentionableUsers() {
        if (!this.state.mentionSearchText.trim()) {
            return this.state.mentionableUsers;
        }
        const search = this.state.mentionSearchText.toLowerCase();
        return this.state.mentionableUsers.filter((user) =>
            user.name.toLowerCase().includes(search)
        );
    }

    onSelectMention(partnerId, userName) {
        // Insertar placeholder en el mensaje
        this.state.chatterMessage += `@${userName} `;

        // Guardar la información de la mención para convertirla a HTML después
        this.state.mentionedPartners.push({
            id: partnerId,
            name: userName,
            text: `@${userName}`,
        });

        this.state.showMentionList = false;
        this.state.mentionSearchText = "";
    }

    onAttachFile() {
        // Crear input file dinámico
        const input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.accept = "*/*";

        input.onchange = (e) => {
            const files = e.target.files;
            if (!files || files.length === 0) return;

            Array.from(files).forEach((file) => {
                const reader = new FileReader();

                reader.onload = (event) => {
                    const base64String = event.target.result.split(",")[1];
                    this.state.chatterAttachments.push({
                        name: file.name,
                        content: base64String,
                        mimetype: file.type || "application/octet-stream",
                    });
                };

                reader.readAsDataURL(file);
            });
        };

        input.click();
    }

    removeAttachment(index) {
        this.state.chatterAttachments.splice(index, 1);
    }

    async onPostMessage() {
        try {
            // Validar que hay contenido
            if (
                !this.state.chatterMessage.trim() &&
                this.state.chatterAttachments.length === 0
            ) {
                this.notification.add("Please write a message or attach a file", {
                    type: "warning",
                });
                return;
            }

            const attachmentIds = [];

            // Crear attachments si existen (sin res_model/res_id para que message_post los vincule al mensaje)
            if (this.state.chatterAttachments.length > 0) {
                for (const attachment of this.state.chatterAttachments) {
                    const attachmentId = await this.orm.create("ir.attachment", [
                        {
                            name: attachment.name,
                            res_model: "stock.picking",
                            res_id: this.state.pickingId,
                            datas: attachment.content,
                            mimetype: attachment.mimetype,
                        },
                    ]);
                    attachmentIds.push(attachmentId[0]);
                }
            }

            // Obtener base URL del sistema
            const baseUrlParam = await this.orm.searchRead(
                "ir.config_parameter",
                [["key", "=", "web.base.url"]],
                ["value"]
            );
            const baseUrl =
                baseUrlParam.length > 0
                    ? baseUrlParam[0].value
                    : window.location.origin;

            // Construir el body con enlaces HTML para las menciones
            let body = this.state.chatterMessage.trim() || "Archivo adjunto";
            const partnerIds = [];

            // Reemplazar cada mención con su enlace HTML
            for (const mention of this.state.mentionedPartners) {
                const mentionLink = `<a href="${baseUrl}/web#model=res.partner&amp;id=${mention.id}" class="o_mail_redirect" data-oe-id="${mention.id}" data-oe-model="res.partner" target="_blank">${mention.text}</a>`;
                body = body.replace(mention.text, mentionLink);
                partnerIds.push(mention.id);
            }

            // Postear el mensaje con HTML
            await this.orm.call(
                "stock.picking",
                "message_post",
                [this.state.pickingId],
                {
                    body: body,
                    message_type: "comment",
                    subtype_xmlid: "mail.mt_note",
                    attachment_ids: attachmentIds,
                    partner_ids: partnerIds,
                    body_is_html: true,
                }
            );

            this.notification.add("Message posted successfully", {type: "success"});

            // Cerrar el chatter
            this.onCloseChatter();
        } catch (error) {
            console.error("Error posting message:", error);
            this.notification.add(error.message || "Error posting message", {
                type: "danger",
            });
        }
    }

    async _showBackorderDialog() {
        try {
            // Calcular las líneas con cantidades pendientes
            const pendingLines = this.state.moveLines
                .filter((line) => line.qty_picked < line.quantity_demand)
                .map((line) => ({
                    product_name: line.product_name,
                    product_code: line.product_code,
                    qty_picked: line.qty_picked,
                    qty_demand: line.quantity_demand,
                    qty_backorder: line.quantity_demand - line.qty_picked,
                    product_uom: line.product_uom,
                }));

            if (pendingLines.length === 0) {
                // No hay cantidades pendientes, esto no debería pasar
                this.notification.add("Picking validated successfully", {
                    type: "success",
                });
                // Volver al formulario del picking
                this.onClose();
                return;
            }

            // Mostrar el diálogo (no necesitamos el wizard ID)
            this.state.backorderPendingLines = pendingLines;
            this.state.showBackorderDialog = true;
        } catch (error) {
            console.error("Error showing backorder dialog:", error);
            this.notification.add("Error showing backorder dialog", {
                type: "danger",
            });
        }
    }

    onCloseBackorderDialog() {
        this.state.showBackorderDialog = false;
        this.state.backorderPendingLines = [];
    }

    async onConfirmBackorder() {
        try {
            // Llamar a button_validate con skip_backorder para crear el backorder
            // sin mostrar el wizard nativo
            await this.orm.call(
                "stock.picking",
                "button_validate",
                [[this.state.pickingId]],
                {
                    context: {
                        skip_backorder: true,
                    },
                }
            );

            this.notification.add("Picking validated with backorder created", {
                type: "success",
            });

            // Cerrar el diálogo y volver al formulario del picking
            this.onCloseBackorderDialog();
            this.onClose();
        } catch (error) {
            console.error("Error confirming backorder:", error);
            this.notification.add(error.message || "Error confirming backorder", {
                type: "danger",
            });
        }
    }

    async onCancelBackorder() {
        try {
            // Llamar a button_validate con picking_ids_not_to_backorder
            // para validar sin crear backorder
            await this.orm.call(
                "stock.picking",
                "button_validate",
                [[this.state.pickingId]],
                {
                    context: {
                        skip_backorder: true,
                        picking_ids_not_to_backorder: [this.state.pickingId],
                    },
                }
            );

            this.notification.add("Picking validated without backorder", {
                type: "success",
            });

            // Cerrar el diálogo y volver al formulario del picking
            this.onCloseBackorderDialog();
            this.onClose();
        } catch (error) {
            console.error("Error canceling backorder:", error);
            this.notification.add(error.message || "Error canceling backorder", {
                type: "danger",
            });
        }
    }
}

registry
    .category("actions")
    .add("stock_barcode_oca.BarcodeInterface", BarcodeInterface);
