# A stand-in for a ParaView Python trace (Tools > Start Trace in ParaView): only the
# camera lines matter to 'flowreel camera import'.
renderView1 = GetActiveViewOrCreate('RenderView')
renderView1.CameraPosition = [-8.0, 6.0, 9.0]
renderView1.CameraFocalPoint = [6.0, 0.0, 0.0]
renderView1.CameraViewUp = [0.0, 1.0, 0.0]
renderView1.CameraViewAngle = 30.0
