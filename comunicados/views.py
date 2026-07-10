from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import es_administrador
from core.views_utils import paginar

from .forms import AvisoForm
from .models import Aviso


@login_required
def aviso_list(request):
    if not es_administrador(request.user):
        messages.error(request, 'Solo un administrador del sistema puede gestionar avisos.')
        return redirect('core:dashboard')

    avisos = Aviso.objects.all().select_related('creado_por')
    return render(request, 'comunicados/aviso_list.html', {'avisos': paginar(request, avisos)})


@login_required
def aviso_form(request, pk=None):
    if not es_administrador(request.user):
        messages.error(request, 'Solo un administrador del sistema puede gestionar avisos.')
        return redirect('core:dashboard')

    aviso = get_object_or_404(Aviso, pk=pk) if pk else None
    if request.method == 'POST':
        form = AvisoForm(request.POST, instance=aviso)
        if form.is_valid():
            nuevo_aviso = form.save(commit=False)
            if not aviso:
                nuevo_aviso.creado_por = request.user
            nuevo_aviso.save()
            form.save_m2m()
            messages.success(request, 'Aviso guardado.')
            return redirect('comunicados:aviso_list')
    else:
        form = AvisoForm(instance=aviso)

    return render(request, 'comunicados/aviso_form.html', {'form': form, 'aviso': aviso})


@login_required
def aviso_toggle(request, pk):
    if not es_administrador(request.user):
        messages.error(request, 'Solo un administrador del sistema puede gestionar avisos.')
        return redirect('core:dashboard')

    aviso = get_object_or_404(Aviso, pk=pk)
    if request.method == 'POST':
        aviso.activo = not aviso.activo
        aviso.save(update_fields=['activo'])
        messages.success(request, f'Aviso {"activado" if aviso.activo else "desactivado"}.')
    return redirect('comunicados:aviso_list')
