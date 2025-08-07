"""API Controller - Provides a quota management interface"""

import json
from webob import Response
from ryu.app.wsgi import ControllerBase, WSGIApplication


class APIController(ControllerBase):
    """API Controller - Provides a quota management interface"""
    
    def __init__(self, req, link, data, **config):
        super(APIController, self).__init__(req, link, data, **config)
        self.quotaManager = data['quotaManager']
        self.trafficMonitor = data['trafficMonitor']
        self.controller = data['controller']
    
    def list_quota_status(self, req, **kwargs):
        """Obtain the quota status of all devices"""
        status = self.quotaManager.getQuotaStatus()
        return Response(content_type='application/json', body=json.dumps(status, indent=2))
    
    def add_quota(self, req, **kwargs):
        """Increase the quota for the devices"""
        try:
            data = json.loads(req.body)
            mac_address = data.get('mac')
            additional_gb = data.get('gb', 0)
            
            if not mac_address or additional_gb <= 0:
                return Response(status=400, body=json.dumps({'error': 'Invalid parameters'}))
            
            bytes_to_add = additional_gb * 1024 * 1024 * 1024
            success = self.quotaManager.addQuotaForDevice(mac_address, bytes_to_add)
            
            if success:
                # Update the flow table immediately after purchasing the traffic
                self._update_all_flows()
                return Response(content_type='application/json', 
                              body=json.dumps({'success': True, 'message': f'Added {additional_gb}GB to {mac_address}'}))
            else:
                return Response(status=404, body=json.dumps({'error': 'Device not found'}))
                
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def reset_traffic(self, req, **kwargs):
        """Reset the device's data usage"""
        try:
            data = json.loads(req.body)
            mac_address = data.get('mac')
            
            if not mac_address:
                return Response(status=400, body=json.dumps({'error': 'MAC address required'}))
            
            success = self.quotaManager.resetDeviceTraffic(mac_address)
            
            if success:
                self._update_all_flows()
                return Response(content_type='application/json', 
                              body=json.dumps({'success': True, 'message': f'Reset traffic for {mac_address}'}))
            else:
                return Response(status=404, body=json.dumps({'error': 'Device not found'}))
                
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def update_flows(self, req, **kwargs):
        """Manually update the flow table (for after purchasing traffic)"""
        try:
            self._update_all_flows()
            return Response(content_type='application/json', 
                          body=json.dumps({'success': True, 'message': 'Flows updated'}))
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
    
    def _update_all_flows(self):
        """Update the flow tables of all connected switches"""
        try:
            for datapath in self.controller.datapaths.values():
                self.controller.flowManager.updateQuotaBasedFlows(datapath, self.controller.quotaManager)
            self.controller.logger.info("all flow update succeed")
        except Exception as e:
            self.controller.logger.error("all flow update faild: %s", str(e))
    
    def get_traffic_stats(self, req, **kwargs):
        """get traffic"""
        try:
            stats = self.trafficMonitor.getQuotaBasedTraffic()
            return Response(content_type='application/json', body=json.dumps(stats, indent=2))
        except Exception as e:
            return Response(status=500, body=json.dumps({'error': str(e)}))
