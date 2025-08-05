"""API控制器 - 提供配额管理接口"""

import json
from webob import Response
from ryu.app.wsgi import ControllerBase, WSGIApplication


class APIController(ControllerBase):
    """API控制器 - 提供配额管理接口"""
    
    def __init__(self, req, link, data, **config):
        super(APIController, self).__init__(req, link, data, **config)
        self.quotaManager = data['quotaManager']
        self.trafficMonitor = data['trafficMonitor']
        self.controller = data['controller']
    
    def list_quota_status(self, req, **kwargs):
        """获取所有设备的配额状态"""
        status = self.quotaManager.getQuotaStatus()
        return Response(content_type='application/json', body=json.dumps(status, indent=2))
    
    def add_quota(self, req, **kwargs):
        """为设备增加配额"""
        try:
            data = json.loads(req.body)
            room_number = data.get('room')
            additional_gb = data.get('gb', 0)
            
            if not room_number or additional_gb <= 0:
                return Response(status=400, body=json.dumps({'error': 'Invalid parameters'}))
            
            bytes_to_add = additional_gb * 1024 * 1024 * 1024
            success = self.quotaManager.addQuotaForRoom(room_number, bytes_to_add)
            
            if success:
                # 购买流量后立即更新流表
                self._update_all_flows()
                return Response(content_type='application/json', 
                              body=json.dumps({'success': True, 'message': f'Added {additional_gb}GB to Room {room_number}'}))
            else:
                return Response(status=404, body=json.dumps({'error': 'Room not found'}))
                
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def reset_traffic(self, req, **kwargs):
        """重置设备流量使用"""
        try:
            data = json.loads(req.body)
            room_number = data.get('room')
            
            if not room_number:
                return Response(status=400, body=json.dumps({'error': 'Room number required'}))
            
            success = self.quotaManager.resetRoomTraffic(room_number)
            
            if success:
                self._update_all_flows()
                return Response(content_type='application/json', 
                              body=json.dumps({'success': True, 'message': f'Reset traffic for Room {room_number}'}))
            else:
                return Response(status=404, body=json.dumps({'error': 'Room not found'}))
                
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def update_flows(self, req, **kwargs):
        """手动更新流表（用于购买流量后）"""
        try:
            self._update_all_flows()
            return Response(content_type='application/json', 
                          body=json.dumps({'success': True, 'message': 'Flows updated'}))
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def _update_all_flows(self):
        """更新所有连接的交换机的流表"""
        try:
            for datapath in self.controller.datapaths.values():
                self.controller.flowManager.updateQuotaBasedFlows(datapath, self.controller.quotaManager)
            self.controller.logger.info("✅ 所有交换机流表已更新")
        except Exception as e:
            self.controller.logger.error("❌ 流表更新失败: %s", str(e))
    
